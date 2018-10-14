import datetime, logging, base64
from PySide import QtCore, QtGui

logger = logging.getLogger('root')

class PixmapContainer(QtGui.QLabel):
    def __init__(self, pixmap, mode='f', parent=None):
        super(PixmapContainer, self).__init__(parent)
        if mode == 'f':
            self._pixmap = QtGui.QPixmap(pixmap)
        elif mode == "b64":
            self._pixmap = QtGui.QPixmap()
            self._pixmap.loadFromData(pixmap)

        self.setMinimumSize(1, 1)  # needed to be able to scale down the image

    def setFromB64(self, data):
        self._pixmap.loadFromData(data)
        self.resizeEvent(None)

    def resizeEvent(self, event):
        w = min(self.width(), self._pixmap.width())
        h = min(self.height(), self._pixmap.height())
        self.setPixmap(self._pixmap.scaled(w, h, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation))


class Window(QtGui.QStackedWidget):
    def __init__(self, application, screenW, screenH):
        QtGui.QStackedWidget.__init__(self)
        self._APP = application

        self.keyboard_buffer = ""

        

        self.setStyleSheet('''
                              QLabel#clock   {font-size: %spt;color: #002266}
                              QLabel#welcome {font-size: %spt}
                              QLabel#statusbar {font-size: %spt;color:white;}
                           ''' % (screenW*0.0625, screenW*0.04165, screenW*0.01562 ))

        self.home = QtGui.QWidget()
        self.login = QtGui.QWidget()
        self.addWidget(self.home)
        self.addWidget(self.login)
        self.init_home()
        self.init_login()

        self.installEventFilter(self)


        self.showFullScreen()

    def init_home(self):
        self.logo = PixmapContainer('res/img/logo.png')
        self.logo.setAlignment(QtCore.Qt.AlignCenter)
        
        self.clock = QtGui.QLabel(datetime.datetime.now().time().strftime("%H:%M:%S"))
        self.clock.setObjectName("clock")
        self.clock.setAlignment(QtCore.Qt.AlignCenter)

        self.welcome = QtGui.QLabel("Benvenuto.\nScansiona il tuo Badge.")
        self.welcome.setObjectName("welcome")
        self.welcome.setAlignment(QtCore.Qt.AlignCenter)

        self.statusbar = QtGui.QLabel("Marcatore di presenza in fase di avviamento....")
        self.statusbar.setObjectName("statusbar")
        self.statusbar.setAlignment(QtCore.Qt.AlignCenter)
        self.statusbar.setMaximumHeight(self.height()*0.15)

        layout = QtGui.QVBoxLayout()
        layout.addWidget(self.logo)
        layout.addWidget(self.clock)
        layout.addWidget(self.welcome)
        layout.addWidget(self.statusbar)

        self.home.setLayout(layout)
		
    def init_login(self):
        self.user_image = PixmapContainer(None)
        self.user_image.setAlignment(QtCore.Qt.AlignCenter)

        self.login_name = QtGui.QLabel("Benvenuto.\nScansiona il tuo Badge.")
        self.login_name.setObjectName("welcome")
        self.login_name.setAlignment(QtCore.Qt.AlignCenter)

        layout = QtGui.QVBoxLayout()
        layout.addWidget(self.user_image)
        layout.addWidget(self.login_name)

        self.login.setLayout(layout)        

    def show_login(self, employee):
        self.user_image.setFromB64(base64.b64decode(employee[2]))
        self.login_name.setText("Benvenuto %s.\nTimbratura registrata alle %s." % (employee[1], datetime.datetime.now().time().strftime("%H:%M:%S")))
        self.setCurrentIndex(1)
        pass

    def show_home(self):
        self.setCurrentIndex(0)
        self.welcome.setStyleSheet('')
        self.welcome.setText("Benvenuto.\nScansiona il tuo Badge.")
        return True

    def show_error(self, error):
        self.welcome.setStyleSheet('''
                              QLabel#welcome {background-color:red}
                           ''')
        self.welcome.setText(error)

    def eventFilter(self, widget, event):
        if (event.type() == QtCore.QEvent.KeyPress):
            key = event.key()

            if key == QtCore.Qt.Key_Enter:
                self.send_kb()
            else:
                try: 
                    self.keyboard_buffer += chr(key)
                except ValueError:
                    self.send_kb()                    

        return QtGui.QWidget.eventFilter(self, widget, event)

    def send_kb(self):
        if self.keyboard_buffer:
            self._APP.receive_barcode(self.keyboard_buffer)
        self.keyboard_buffer = ""

    def tick(self):
        self._set_clock_time(datetime.datetime.now().time())
        self._set_status()

    def _set_clock_time(self, clock):
        self.clock.setText(clock.strftime("%H:%M:%S"))

    def _set_status(self):
        haslocal = self._APP._CON.haslocal
        status = self._APP._CON.status

        msg, color = "", ""

        if haslocal:
            if status == 0:
                msg = "Marcatempo OK, connessione al server in corso..."
                color = "blue"
            elif status == 1:
                msg = "Marcatempo OK, server offline. Tentativo di riconnessione in corso..."
                color = "yellow"
            elif status == 2:
                msg = "Marcatempo OK, connessione buona."
                color = "green"
            elif status == 3:
                msg = "Credenziali invalide. Contattare l'ufficio risorse umane. E' possibile marcare la presenza."
                color = "orange"
            else:
                msg = "Errore imprevisto. Contattare l'ufficio risorse umane. E' possibile marcare la presenza."
                color = "orange"
        
        else:
            if status == 0:
                msg = "Marcatempo in avviamento, attendere..."
                color = "gray"
            elif status == 1:
                msg = "DB Locale assente. Connessione al server in corso..."
                color = "orange"
            elif status == 2:
                msg = "Inizializzazione, connesso al server..."
                color = "blue"
            elif status == 3:
                msg = "Credenziali invalide, database assenti. Il Marcatempo sara' inutilizzabile."
                color = "red"
            else:
                msg = "Errore imprevisto. Il Marcatempo sara' inutilizzabile."
                color = "red"
        
        self.statusbar.setStyleSheet("QLabel {background-color:%s}" % color)
        self.statusbar.setText(msg)