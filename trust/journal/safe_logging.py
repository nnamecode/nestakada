"""Finite event vocabulary. Never formats messages, arguments or exceptions."""
import json
import logging

EVENTS = frozenset({'AUTH_REJECTED','INPUT_REJECTED','IDENTITY_FAILURE',
    'WRITE_REJECTED','TRUST_UNAVAILABLE','UNEXPECTED_FAILURE','PROCESS_MESSAGE'})
LEVELS = {10:'DEBUG',20:'INFO',30:'WARNING',40:'ERROR',50:'CRITICAL'}

class SafeFormatter(logging.Formatter):
    def format(self,record):
        values=record.__dict__
        event=values.get('trust_event')
        if type(event) is not str or event not in EVENTS: event='PROCESS_MESSAGE'
        number=values.get('levelno')
        level=LEVELS.get(number,'ERROR') if type(number) is int else 'ERROR'
        return json.dumps({'event':event,'level':level,'result':'observed' if event=='PROCESS_MESSAGE' else 'rejected'},separators=(',',':'))

def failure(event):
    logging.getLogger('trust.endpoint').error('',extra={'trust_event':event})
