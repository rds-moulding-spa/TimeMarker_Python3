VERSION = "A-1"

config = {
    #Marker
    'marker_id':        1,
    'logfile':          'logging.log',
    #Connection
    'server_address':   'http://127.0.0.1',
    'server_port':      '8069',
    'db':               'db',
    'username':         'user@foo.com',
    'password':         'foo',
    #UI
    'ui_style':         'Material',
    #CLOCKS
    'tick_time':        0.2,#s
    #Datetime
    'datetime_format':  "%Y-%m-%d %H:%M:%S"
}

# RISERVATO

def get_cparam():
    return [
            config['marker_id'],
            config['server_address'] + (":%s" % config['server_port']) if config['server_port'] else "",
            config['db'],
            config['username'],
            config['password'],
           ]