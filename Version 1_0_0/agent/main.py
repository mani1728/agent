class AgentWorker:
    def __init__(self, transport: ITransportClient, mt5_manager):
        self.transport = transport
        self.mt5 = mt5_manager
        self.running = False

    def run(self, stop_event):
        self.transport.start()
        while not stop_event.is_set():
            # ۱. دریافت فرامین مستقل از اینکه از کجا آمده‌اند
            commands = self.transport.poll_commands(timeout_sec=1.0)

            for cmd in commands:
                # ۲. اجرا بر روی MT5
                try:
                    method = getattr(self.mt5, cmd.target_method)
                    result_data = method(**cmd.params)

                    response = ResponseEnvelope(
                        correlation_id=cmd.correlation_id,
                        status="success",
                        data=result_data
                    )
                except Exception as ex:
                    response = ResponseEnvelope(
                        correlation_id=cmd.correlation_id,
                        status="error",
                        error_message=str(ex)
                    )

                # ۳. ارسال پاسخ
                if self.transport.send_response(response):
                    self.transport.ack_command(cmd.command_id)

        self.transport.stop()
