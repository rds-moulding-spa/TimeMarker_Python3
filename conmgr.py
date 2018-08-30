import sys, os, logging, datetime, time, sqlite3
from xmlrpc import client as xcl
import config as _C

class EmployeeNotFound(Exception):
    pass

class EmployeeForbiddenException(Exception):
    pass

logger = logging.getLogger('root')

def utcdate():
    return datetime.datetime.utcnow().strftime(_C.config['datetime_format'])

#Handlers

def withdb(func):
    def _withdb(self, *args, **kwargs):
        self.db_start()
        try:
            a = func(self, *args, **kwargs)
            self.db_stop()
            return a
        except Exception:
            self.db_stop(False)
            raise
    return _withdb

def handled_connection(func):
    def _handled_connection(self, *args, **kwargs):
        try:
            result = func(self, *args, **kwargs)
            return result
        except (ConnectionAbortedError, ConnectionResetError, ConnectionRefusedError, ConnectionError, TypeError) as e:
            logger.warning("Transazione abortita! Nuovo tentativo in corso...")
            return False

    return _handled_connection

class ConnectionManager(object):
    def __init__(self, application, mid, adr, db, usr, psw):
        self._APP = application
        self.mid = mid
        self.url, self.db = adr, db
        self.usr, self.psw = usr, psw
        self.status = 0
        self.dblocked = False
        self.uid = None
        self.haslocal = False
        
        
        logger.info("Carico connessioni XML-RPC...")
        try:
            self.common = xcl.ServerProxy('{}/xmlrpc/2/common'.format(self.url))
            self.models = xcl.ServerProxy('{}/xmlrpc/2/object'.format(self.url))
        except Exception:
            raise ValueError('Errore nella creazione degli oggetti XML-RPC.')

        self._APP.register_timer("reauth", self.authenticate, [],  interval=8000)
        
        try:   
            self.check_db()
            self.haslocal = True        
        except sqlite3.OperationalError:
            self.haslocal = False
            logger.warning("Database locale assente, inizializzo...")
            self._APP.register_timer("db_init", self.db_init, [], onsuccess_destroy=True, interval=2000)     

        self._APP.register_timer("markings_check", self.check_unsent_markings, [],  interval=20000) 
        self._APP.register_timer("db_rebase", self.db_init, [],  interval=600000)   

    #Connections
    
    def keepalive(self):
        self._APP.register_timer("keepalive", self._keepalive, [], interval=2000) 

    def _keepalive(self):
        try:
            self.common.version()
            self.status = 2
        except ConnectionRefusedError:
            self.status = 1
            logger.info("Connessione al server persa!")
            self._APP.unregister_timer("keepalive")
            self._APP.register_timer("reauth", self.authenticate, [], interval=8000) 

    def authenticate(self):
        logger.info("Connessione al server in corso...")
        try:
            self.uid = self.common.authenticate(self.db, self.usr, self.psw, {})
        except ConnectionRefusedError:
            logger.warning("Autenticazione fallita sul server %s, db=%s, usr=%s, psw=%s. Nuovo tentativo tra 10 secondi..." % (self.url, self.db, self.usr, self.psw))
            
            self.uid = None
            
        if self.uid:
            self.status = 2
            logger.info("Connessione XML-RPC effettuata con successo. Autenticato.")
            self._APP.unregister_timer("reauth")
            self._APP.register_timer("keepalive", self._keepalive, [], interval=1000)
            self._APP.start_listen()
           
        elif self.uid == False:
            self.status = 3
            logger.critical("Autenticazione rifiutata sul server %s, db=%s, usr=%s, psw=%s!" % (self.url, self.db, self.usr, self.psw))
        elif self.uid == None:
            self.status = 1

    #Local db 
       
    @withdb
    def check_db(self):
        logger.info("Verifico il database locale...")
        self.cur.execute("SELECT count(*) from employees;")
        logger.info("Database locale disponibile.")
        self._APP.start_listen()

    @withdb
    def check_unsent_markings(self):
        logger.info("Verifico marcature presenti in locale...")
        self.cur.execute("SELECT id, employee_id, datetime FROM markings ORDER BY datetime ASC;")
        markings = self.cur.fetchall()
        if bool(markings) and (self.status == 2):
            logger.info("Trovate %d marcature, invio..." % len(markings))
            self._APP.register_timer("markings_send", self.send_deferred_markings, [markings], onsuccess_destroy=True, interval=2000) 
    
    @handled_connection
    def send_deferred_markings(self, markings):
        stack = self.execute_kw('rds.hr.timemarker', 'read_markings', [markings])
        self.clean_accepted_markings(stack)
        logger.info("Inviate %d marcature con successo su %d." % (len(stack), len(markings)))
        return True
    
    @withdb
    def clean_accepted_markings(self, ids):
        query = "DELETE FROM markings WHERE id IN (%s);" % ','.join(list(map(lambda x: str(x), ids)))
        self.cur.execute(query)
    
    @handled_connection
    @withdb
    def db_init(self):
        self.cur.execute("DROP TABLE IF EXISTS employees;")
        self.cur.execute("CREATE TABLE employees (id integer, name string, barcode string, image blob, write_date string);")
        self.cur.execute("CREATE TABLE IF NOT EXISTS markings (id INTEGER PRIMARY KEY AUTOINCREMENT, employee_id integer, datetime string);")

        try:
            employees = self.execute_kw('rds.hr.timemarker', 'download_employees', [[self.mid]])
            if not employees:
                raise ValueError
        except Exception as e:
            logger.debug(e)
            return self.haslocal
        
        self.cur.executemany('INSERT INTO employees VALUES (?,?,?,?,?)', employees)
        logger.warning("Database locale inizializzato!")
        self.haslocal = True
        return self.haslocal
        

    def db_sendmarkings(self):
        query = "SELECT employee_id, datetime from markings"
        self.cur.execute(query)
        markings = self.cur.fetchall()
        logger.info(markings)

    def db_start(self):
        self.localdb = sqlite3.connect('cache/local.db')
        self.cur = self.localdb.cursor()

        while self.dblocked:
            time.sleep(_C.config['tick_time'])
            
        self.dblocked = True
    
    def db_stop(self, commit=True):
        if commit:
            self.localdb.commit()

        self.localdb.close()
        self.dblocked = False
    
    #Operational

    def execute_kw(self, *args):
        if self.status != 2:
            raise ConnectionError("Connessione Assente...")

        return self.models.execute_kw(self.db, self.uid, self.psw, *args)
        

    def read_barcode(self, barcode):
        logger.info("Scansionato badge: %s. Verifico esistenza." % barcode)
        barcode = self.parse_barcode(barcode)
        return self.find_employee(barcode)


    def parse_barcode(self, barcode):
        def get_barcode_array(barcode):
            try:
                return (barcode, str(int(barcode[4:], 16)).zfill(10), str(int(barcode[3:], 16)).zfill(10))
            except ValueError:
                return ()
        barcode_array = get_barcode_array(barcode.zfill(10))
        return barcode_array

    @withdb
    def find_employee(self, barcode_array):
        query = "SELECT id, name, image from employees WHERE barcode IN %s;" % str(barcode_array)
        self.cur.execute(query)
        employee = self.cur.fetchone()
        
        if employee:
            self._APP.register_timer("register_marking", self.register_marking, [employee[0]], onsuccess_destroy=True, interval=400)  
        else:
            raise EmployeeNotFound("Il badge scansionato\nnon corrisponde ad alcun dipendente!")

        return employee

    @withdb   
    def register_marking(self, employee_id):
        date = utcdate()
        logger.info('Tento di autenticare il dipendente %s alle ore %s' % (employee_id, date))
        try:
            stack = self.execute_kw('rds.hr.timemarker', 'read_markings', [[[0, employee_id, date]]])
            logger.info('Autenzicazione effettuata: %s alle ore %s' % (employee_id, date))
            logger.info(stack)
        except (TypeError, ConnectionRefusedError, ConnectionError):
            self.cur.execute('INSERT INTO markings (employee_id, datetime) VALUES ("%s", "%s")' % (employee_id, date))
            logger.info('Autenzicazione fallita, registro in locale: %s alle ore %s' % (employee_id, date))

        return True
