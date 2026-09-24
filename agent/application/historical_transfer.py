"""Checkpointed, read-only history transfer using the existing durable outbox."""
from __future__ import annotations
from agent.contracts.historical import chunk_records

class HistoricalTransfer:
    def __init__(self,state,reader): self._state=state; self._reader=reader
    def run_partition(self, request, partition_index):
        checkpoint=self._state.history_checkpoint(request.transfer_id)
        if checkpoint is not None and partition_index <= checkpoint: return ()
        start,end=tuple(request.partitions())[partition_index]
        chunks=[]
        for chunk in chunk_records(request.transfer_id,self._reader.read(request.symbol,request.data_type,start,end),request.chunk_bytes):
            self._state.enqueue_outbox("historical.chunk",chunk.envelope(),f"{request.transfer_id}:{partition_index}:{chunk.index}")
            chunks.append(chunk)
        self._state.save_history_checkpoint(request.transfer_id,partition_index)
        return tuple(chunks)
