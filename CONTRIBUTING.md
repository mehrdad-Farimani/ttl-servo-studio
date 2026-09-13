# Contributing

Please describe the problem or proposed feature in a GitHub issue. For connection reports, include the operating system, adapter, exact servo model, selected baud, supply voltage, and whether the issue occurs with one servo. Do not attach credentials or private logs.

For a new model profile, provide manufacturer documentation for voltage, protocol, word byte order, register map and position range. Add tests for limits and mixed-model operation, and distinguish physical testing from protocol-only validation. STS, RS485 and PWM support requires separate protocol work, not a renamed SCSCL profile.

Keep all serial I/O off the UI thread. Never add automatic movement on startup, discovery, pose loading, profile assignment or reconnection. Retry reads only; do not blindly resend writes. Keep user data outside application files.

Run `python -m unittest discover -s tests -v` before submitting a pull request. Include the hardware and operating systems actually tested.
