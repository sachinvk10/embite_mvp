EmbITE

EmbITE — Embedded Integrated Test Environment

EmbITE is a reusable validation automation framework for embedded platforms.

It allows validation engineers to define WHAT to test using simple .tst DSL actions, while the framework handles HOW to execute the validation on the DUT.

Current MVP

Project-based configuration

SSH-based DUT connection

Reusable BoardActions

DSL-based .tst execution

Parser, Executor and Action Registry

Project-specific logging and reporting

Raspberry Pi 5 validation

RK3588 project structure

Current DSL Actions

GET_HOSTNAME
GET_IP_ADDRESS
GET_OS
GET_KERNEL
GET_ARCHITECTURE
GET_MEMORY

Repository Structure

embite_mvp/
├── board_actions/
├── lib/
├── manual/
├── projects/
│   ├── raspberry_pi5/
│   └── rk3588/
├── src/
└── utility/

Each project contains:

project/
├── config/
│   └── project.yaml
├── tests/
│   └── *.tst
└── report/
    └── runs/

The report directory is created automatically during execution.

Run

Activate the virtual environment:

source .venv/bin/activate

Run Raspberry Pi 5:

python -m src.embite projects/raspberry_pi5

Run RK3588:

python -m src.embite projects/rk3588

Execution Flow

project.yaml
    ↓
.tst File
    ↓
Parser
    ↓
Executor
    ↓
Action Registry
    ↓
Board / Validation API
    ↓
BoardActions
    ↓
DUT

Logging

Each execution creates one project-specific timestamped log:

projects/raspberry_pi5/report/runs/
└── raspberry_pi5_<timestamp>.log

Logs are available both on the console and in the run log file.

Next

USB validation

Serial connectivity

PCIe validation

Storage validation

Networking validation

Performance and boot validation
