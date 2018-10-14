VERSION = "A-1"

config = {
    #Marker
    'marker_id':        1,
    'logfile':          'logging.log',
    #Connection
    'server_address':   'http://10.15.0.112',
    'server_port':      '8069',
    'db':               'rdsdb',
    'username':         'alfredo.salata@rdsmoulding.com',
    'password':         'ace0896AC21!!',
    #UI
    'ui_style':         'Material',
    #CLOCKS
    'tick_time':        0.2,#s
    #Datetime
    'datetime_format':  "%Y-%m-%d %H:%M:%S",
    'service_thread':   True
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
