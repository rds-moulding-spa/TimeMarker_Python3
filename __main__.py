import sys, os, logging, datetime, time, sqlite3, random
import xmlrpclib as xcl

from PySide import QtCore, QtGui
from threading import Thread

import config as _C
import conmgr, uimgr

class ServiceThread(QtCore.QThread):
    def run(self):
        self.exec_()
    

class Application(QtGui.QApplication):
    def __init__(self, *args):
        super(Application, self).__init__(*args)

        t = self.desktop().screenGeometry()
        
        self._timers = list()
        self.listen = False
        self.serviceThread = ServiceThread() if _C.config['service_thread'] else None
        if self.serviceThread:
            self.serviceThread.start()

        self._UI = uimgr.Window(self, t.width(), t.height())
        self._CON = conmgr.ConnectionManager(self, *_C.get_cparam())
        self.register_timer("uihandler", self._UI.tick, [], interval=400)        
        

    def start_listen(self):
        self.listen = True
        return True
      
    def receive_barcode(self, barcode):
        barcode = str(barcode)
        if len(barcode) != 10:
            logging.warning("Lunghezza rfid %s scorretta!", barcode)
            barcode = barcode.zfill(10)

        if self.listen == False:
            return
        
        self.listen == False

        logger.info("Letto rfid %s, invio al manager di connessione..." % barcode)
        try:
            result = self._CON.read_barcode(barcode)
        except Exception as e:
            self._UI.show_error(str(e))
            result = False

                    
        self.listen = False
        self.register_timer("listen", self.start_listen, [], onsuccess_destroy=True, interval=2000)

        self.unregister_timer("showhome")
        self.register_timer("showhome", self._UI.show_home, [], onsuccess_destroy=True, interval=5000)

        if result:
            self._UI.show_login(result)



    def register_timer(self, name, slot, args=[], ondestroy=None, ondestroy_args=[], onsuccess_destroy=False, count=0, interval=_C.config['tick_time'], service=False):
        if count < 0:
            raise ValueError("Il numero di iterazioni deve essere zero (infinito) o maggiore di zero!")
        
        if not name:
            name = self.get_new_timer_name()

        timer = QtCore.QTimer()
        timer.name = name
        
        if count > 0:
            class context:
                counter = 0

            def handler():
                context.counter += 1
                a = slot(*args)
                if (onsuccess_destroy and a) or (context.counter >= count):
                    timer.stop()
                    self._timers.remove(timer)
                    timer.deleteLater()
        else:
            def handler():
                a = slot(*args)
                if (onsuccess_destroy and a):
                    timer.stop()
                    self._timers.remove(timer)
                    timer.deleteLater()
            

        timer.timeout.connect(handler)
        if ondestroy:
            timer.destroyed.connect(lambda: ondestroy(*ondestroy_args))
        

        timer.start(interval)
        if service:
            timer.moveToThread(self.serviceThread)

        self._timers.append(timer)

        return timer
    
    def unregister_timer(self, name):
        if name in map(lambda x: x.name, self._timers):
            try:
                timers = list(filter(lambda x: x.name == name, self._timers))
                for timer in timers:
                    timer.stop()
                    self._timers.remove(timer)
                    timer.deleteLater()
                return True

            except Exception as e:
                logger.exception(e)
        else:
            return False
    
    def get_new_timer_name(self):
        name = random.getrandbits(64)
        while (name in map(lambda x: x.name, self._timers)):
            name = random.getrandbits(64)
        return name


if __name__ == "__main__":

    logger = logging.getLogger('root')
    logger.setLevel(logging.INFO)

    # create file handler which logs even debug messages
    fh = logging.FileHandler('logging.log')
    fh.setLevel(logging.DEBUG)

    # create console handler with a higher log level
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)

    # create formatter and add it to the handlers
    formatter = logging.Formatter('%(asctime)s %(levelname)s: %(message)s', datefmt='%m/%d/%Y %H:%M:%S')
    fh.setFormatter(formatter)
    ch.setFormatter(formatter)

    # add the handlers to the logger
    logger.addHandler(fh)
    logger.addHandler(ch)

    logger.info("Marcatempo RDS in avvio. ID: %d" % _C.config['marker_id'])

    _APP = Application(sys.argv)
    #_ENG = QtQml.QQmlApplicationEngine()

    #_CTX = _ENG.rootContext()
    #_CTX.setContextProperty('uimgr', _APP._UI)
    #_ENG.load('views/main.qml')

    #if not _ENG.rootObjects():
    #    sys.exit(-1)
    _APP._UI.show()
    sys.exit(_APP.exec_())

