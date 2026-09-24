"""Bounded, UTC-only historical transfer contracts."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json

def utc(value: datetime) -> datetime:
    if value.tzinfo is None: raise ValueError("historical timestamps must be timezone-aware")
    return value.astimezone(timezone.utc)

@dataclass(frozen=True)
class HistoricalRequest:
    transfer_id: str; symbol: str; data_type: str; start: datetime; end: datetime; partition_span: timedelta; chunk_bytes: int
    def __post_init__(self):
        if self.data_type not in {"rates", "ticks"}: raise ValueError("unsupported historical data type")
        if not self.transfer_id or not self.symbol or self.partition_span <= timedelta(0) or self.chunk_bytes <= 0: raise ValueError("invalid historical request")
        object.__setattr__(self,"start",utc(self.start)); object.__setattr__(self,"end",utc(self.end))
        if self.end < self.start: raise ValueError("historical end precedes start")
    def partitions(self):
        current=self.start
        while current < self.end:
            end=min(current+self.partition_span,self.end); yield (current,end); current=end

@dataclass(frozen=True)
class HistoricalChunk:
    transfer_id: str; index: int; records: tuple[dict,...]; complete: bool=False
    def payload(self): return json.dumps({"transfer_id":self.transfer_id,"index":self.index,"records":self.records,"complete":self.complete},sort_keys=True,separators=(",",":"),ensure_ascii=True).encode()
    @property
    def checksum(self): return sha256(self.payload()).hexdigest()
    def envelope(self): return {"transfer_id":self.transfer_id,"index":self.index,"record_count":len(self.records),"checksum_sha256":self.checksum,"complete":self.complete,"payload":self.payload().decode()}
    def verify(self): return sha256(self.payload()).hexdigest()==self.checksum

def chunk_records(transfer_id: str, records, max_bytes: int):
    """Stream records into bounded canonical chunks; never materialize an MT5 range."""
    batch=[]; index=0
    for record in records:
        candidate=batch+[dict(record)]
        if batch and len(json.dumps(candidate,sort_keys=True,separators=(",",":"),ensure_ascii=True).encode()) > max_bytes:
            yield HistoricalChunk(transfer_id,index,tuple(batch)); index+=1; batch=[dict(record)]
        else: batch=candidate
    if batch: yield HistoricalChunk(transfer_id,index,tuple(batch),True)
    else: yield HistoricalChunk(transfer_id,index,(),True)
