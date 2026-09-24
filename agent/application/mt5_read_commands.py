"""First pure-READ MT5 command slice.  No symbol selection or subscriptions."""
from agent.adapters.mt5_adapter import MT5ReadError

READ_COMMANDS = {
    "mt5.get_terminal_information": ("terminal_information", "terminal_info"),
    "mt5.get_terminal_version": ("terminal_version", "version"),
    "mt5.get_account_information": ("account_information", "account_info"),
}
def build_mt5_read_handlers(adapter):
    handlers={}
    for identifier,(method,_api) in READ_COMMANDS.items():
        def handler(command, method=method):
            if dict(command.payload): return {"error":{"code":"READ_REQUEST_PAYLOAD_NOT_ALLOWED","domain":"validation","retryable":False,"ambiguous":False,"details":{}}}
            try: return {"result": getattr(adapter, method)()}
            except MT5ReadError as exc: return {"error":{"code":exc.code,"domain":"mt5","retryable":True,"ambiguous":False,"details":exc.details}}
        handlers[identifier]=handler
    return handlers
