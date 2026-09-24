"""Windows Named Pipe transport with a DACL limited to the current user."""
from __future__ import annotations
import json
import os
import win32api, win32con, win32file, win32pipe, win32security

class WindowsNamedPipe:
    def __init__(self,name):
        if os.name!='nt' or not name or any(c in name for c in '\\/'): raise ValueError('invalid Windows pipe name')
        self.path='\\\\.\\pipe\\'+name
    @staticmethod
    def _security_attributes():
        token=win32security.OpenProcessToken(win32api.GetCurrentProcess(),win32con.TOKEN_QUERY)
        sid=win32security.GetTokenInformation(token,win32security.TokenUser)[0]
        acl=win32security.ACL(); acl.AddAccessAllowedAce(win32security.ACL_REVISION,win32con.GENERIC_ALL,sid)
        descriptor=win32security.SECURITY_DESCRIPTOR(); descriptor.SetSecurityDescriptorDacl(1,acl,0)
        attributes=win32security.SECURITY_ATTRIBUTES(); attributes.SECURITY_DESCRIPTOR=descriptor
        return attributes
    def create_server(self):
        return win32pipe.CreateNamedPipe(self.path,win32pipe.PIPE_ACCESS_DUPLEX,win32pipe.PIPE_TYPE_MESSAGE|win32pipe.PIPE_READMODE_MESSAGE|win32pipe.PIPE_WAIT,1,65536,65536,5000,self._security_attributes())
    def connect_client(self):
        return win32file.CreateFile(self.path,win32con.GENERIC_READ|win32con.GENERIC_WRITE,0,None,win32con.OPEN_EXISTING,0,None)
    @staticmethod
    def send(handle,value):
        raw=json.dumps(value,sort_keys=True,separators=(',',':')).encode(); win32file.WriteFile(handle,raw)
    @staticmethod
    def receive(handle):
        _,raw=win32file.ReadFile(handle,65536); return json.loads(raw.decode())
