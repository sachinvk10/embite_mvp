# EmbITE MVP

EmbITE - Embedded Integrated Test Environment

Enterprise validation framework for embedded and semiconductor systems.

## Architecture

- `board_action/` - Host to DUT connection and control
- `lib/` - Domain-specific validation APIs
- `tests/` - Test cases
- `configs/` - Test and DUT configuration
- `reports/` - Test execution reports
- `docs/` - Documentation

## Initial Target

Raspberry Pi 5

Host:
- Windows
- WSL2 Ubuntu

DUT:
- Raspberry Pi 5
- SSH connection

## Initial Milestone

Windows → WSL2 → SSH → Raspberry Pi 5 → Linux shell → command execution
