EmbITE MVP — User Guide

1. Purpose

EmbITE (Embedded Intelligent Test Environment) is an embedded validation framework that allows a validation engineer to describe test intent using simple DSL actions inside .tst files.

The current MVP supports project-based execution. Each project contains:

A project.yaml file with project and DUT connection details.

One or more .tst files containing EmbITE DSL actions.

A list of which .tst files should execute for that project.

The framework then:

Loads the project configuration.

Connects to the DUT.

Detects the DUT environment.

Reads the selected .tst files.

Parses the DSL actions.

Executes the actions on the DUT.

Displays PASS/FAIL results.

2. Current Repository Structure

Example:

embite_mvp/
│
├── src/
│   └── embite.py
│
├── board_action/
│   ├── connection.py
│   ├── ssh_connection.py
│   ├── shell_detector.py
│   └── command_executor.py
│
├── config/
│   └── config_manager.py
│
├── executor/
│   ├── test_parser.py
│   ├── test_executor.py
│   └── action_registry.py
│
├── lib/
│   └── system_info.py
│
├── projects/
│   ├── raspberry_pi5/
│   │   ├── config/
│   │   │   └── project.yaml
│   │   └── tests/
│   │       ├── system.tst
│   │       └── USB.tst
│   │
│   └── rk3588/
│       ├── config/
│       │   └── project.yaml
│       └── tests/
│           ├── system.tst
│           └── USB.tst
│
├── requirements.txt
└── README.md

The folder structure above reflects the current MVP implementation. The framework will later be reorganized into the finalized EmbITE architecture.

3. Activate the Python Virtual Environment

Open WSL Ubuntu and go to the EmbITE repository:

cd ~/workdir/embite_mvp

Activate the virtual environment:

source .venv/bin/activate

Your terminal prompt should look similar to:

(.venv) sachin@WINDOWS-59HRHCF:~/workdir/embite_mvp$

Verify Python:

which python

Example:

/home/sachin/workdir/embite_mvp/.venv/bin/python

If dependencies are not installed yet:

pip install -r requirements.txt

4. Create a New Project

Each validation target should have its own project directory under:

projects/

Example:

mkdir -p projects/project_a/config
mkdir -p projects/project_a/tests

The resulting structure is:

projects/
└── project_a/
    ├── config/
    │   └── project.yaml
    └── tests/

5. Configure project.yaml

Create:

nano projects/project_a/config/project.yaml

Example for an SSH-connected DUT:

project:
  name: project_a
  description: EmbITE validation project

dut:
  name: raspberry_pi_5
  platform: raspberry_pi_5

  connection:
    type: ssh
    host: 192.168.29.234
    port: 22
    username: pi
    password_prompt: true

tests:
  - tests/system.tst

Configuration Fields

Project

project:
  name: project_a
  description: EmbITE validation project

name — Project name.

description — Short description of the validation project.

DUT

dut:
  name: raspberry_pi_5
  platform: raspberry_pi_5

name — Logical DUT name.

platform — DUT platform or board type.

Connection

connection:
  type: ssh
  host: 192.168.29.234
  port: 22
  username: pi
  password_prompt: true

Current MVP execution supports SSH.

type — Connection mechanism.

host — DUT IP address.

port — SSH port.

username — DUT login username.

password_prompt — If true, EmbITE asks for the password at runtime.

The password is not stored in project.yaml.

Tests

tests:
  - tests/system.tst

Only the .tst files listed here are executed.

For example, if the project contains:

tests/
├── system.tst
├── USB.tst
├── PCIE.tst
└── SATA.tst

but project.yaml contains:

tests:
  - tests/system.tst
  - tests/USB.tst

then only:

system.tst
USB.tst

will execute.

6. Create a .tst File

Create a test file under the project's tests/ directory.

Example:

nano projects/project_a/tests/system.tst

Add the required EmbITE DSL actions:

GET_HOSTNAME
GET_IP_ADDRESS
GET_OS
GET_KERNEL
GET_ARCHITECTURE
GET_MEMORY

Save the file.

Verify:

cat projects/project_a/tests/system.tst

Expected:

GET_HOSTNAME
GET_IP_ADDRESS
GET_OS
GET_KERNEL
GET_ARCHITECTURE
GET_MEMORY

7. Current Supported System DSL Actions

The current MVP supports the following reusable DSL APIs:

DSL Action

Purpose

GET_HOSTNAME

Get DUT hostname

GET_IP_ADDRESS

Get DUT IP address

GET_OS

Get operating system information

GET_KERNEL

Get Linux kernel version

GET_ARCHITECTURE

Get DUT architecture

GET_MEMORY

Get DUT memory information

These DSL actions are reusable in any .tst file.

For example, a future USB.tst may contain both board-level and USB DSL actions:

GET_HOSTNAME
GET_KERNEL

USB_DETECT
USB_GET_INFO
USB_GET_SPEED

GET_MEMORY

The .tst filename does not restrict which DSL APIs can be used inside it.

8. Run the Raspberry Pi 5 Project

From the EmbITE repository root:

cd ~/workdir/embite_mvp

Activate the virtual environment:

source .venv/bin/activate

Run:

python -m src.embite projects/raspberry_pi5

EmbITE automatically reads:

projects/raspberry_pi5/config/project.yaml

and executes only the .tst files listed in that configuration.

9. Example Execution Flow

The current project execution flow is:

python -m src.embite projects/raspberry_pi5
                    │
                    ▼
         projects/raspberry_pi5
                    │
                    ▼
            config/project.yaml
                    │
          ┌─────────┴─────────┐
          │                   │
          ▼                   ▼
     DUT details          Test list
          │                   │
          ▼                   ▼
    SSH connection        system.tst
                              │
                              ▼
                         Test Parser
                              │
                              ▼
                        Test Executor
                              │
                              ▼
                       Action Registry
                              │
                              ▼
                         SystemInfo
                              │
                              ▼
                      Command Executor
                              │
                              ▼
                       SSH Connection
                              │
                              ▼
                             DUT

10. Example Output

Example Raspberry Pi 5 execution:

==================================================
           EmbITE MVP
==================================================
Project path: projects/raspberry_pi5
Loading project configuration:
projects/raspberry_pi5/config/project.yaml

Project: raspberry_pi5
DUT: raspberry_pi_5
Connection type: ssh
Enter password:

Connecting to DUT...
SSH connection established.

DUT OS: Linux
DUT Shell: bash
DUT Shell Path: /bin/bash

Configured test files:
  - tests/system.tst

==================================================
Executing Test File: tests/system.tst
==================================================

Actions:
['GET_HOSTNAME',
 'GET_IP_ADDRESS',
 'GET_OS',
 'GET_KERNEL',
 'GET_ARCHITECTURE',
 'GET_MEMORY']

Test Results
--------------------------------------------------
Action : GET_HOSTNAME
Status : PASS
Result : raspberrypi
--------------------------------------------------
Action : GET_IP_ADDRESS
Status : PASS
Result : 192.168.29.234 ...
--------------------------------------------------
Action : GET_OS
Status : PASS
Result : Debian GNU/Linux 12 (bookworm)
--------------------------------------------------
Action : GET_KERNEL
Status : PASS
Result : 6.12.96+rpt-rpi-2712
--------------------------------------------------
Action : GET_ARCHITECTURE
Status : PASS
Result : aarch64
--------------------------------------------------
Action : GET_MEMORY
Status : PASS
Result : ...
--------------------------------------------------

SSH connection closed.
EmbITE project 'raspberry_pi5' completed.

11. Run the RK3588 Project

Configure:

projects/rk3588/config/project.yaml

with the actual RK3588 DUT connection details.

Example:

project:
  name: rk3588
  description: EmbITE validation project for RK3588

dut:
  name: rk3588
  platform: rk3588

  connection:
    type: ssh
    host: <RK3588_IP_ADDRESS>
    port: 22
    username: <RK3588_USERNAME>
    password_prompt: true

tests:
  - tests/system.tst

Replace:

<RK3588_IP_ADDRESS>
<RK3588_USERNAME>

with the actual values.

Then run:

python -m src.embite projects/rk3588

The same EmbITE DSL framework is reused for the RK3588 project.

12. Execute Multiple .tst Files

Suppose Project A contains:

projects/project_a/tests/
├── system.tst
├── USB.tst
├── PCIE.tst
└── SATA.tst

Configure:

tests:
  - tests/system.tst
  - tests/USB.tst
  - tests/PCIE.tst

EmbITE executes them in the configured order:

system.tst
    ↓
USB.tst
    ↓
PCIE.tst

SATA.tst will not run because it is not listed.

13. Add a New Test File

Create:

nano projects/project_a/tests/new_test.tst

Add supported DSL actions:

GET_HOSTNAME
GET_KERNEL
GET_MEMORY

Then add the file to:

projects/project_a/config/project.yaml

Example:

tests:
  - tests/system.tst
  - tests/new_test.tst

Run:

python -m src.embite projects/project_a

EmbITE will execute both files sequentially.

14. Important Rules

Run from the Repository Root

Run EmbITE from:

~/workdir/embite_mvp

Example:

python -m src.embite projects/raspberry_pi5

Activate the Virtual Environment

Before running:

source .venv/bin/activate

Do Not Store Passwords in YAML

Use:

password_prompt: true

EmbITE will request the DUT password at runtime.

Only Listed Tests Execute

A .tst file existing under tests/ does not mean it will automatically run.

It must be listed under:

tests:

in project.yaml.

DSL Actions Are Reusable

DSL APIs can be mixed across .tst files.

A future USB.tst may use:

GET_HOSTNAME
GET_KERNEL
USB_DETECT
GET_MEMORY

The .tst file represents a validation scenario, not a DSL namespace.

15. Current MVP Scope

Currently verified:

Project configuration       ✅
Project-driven execution    ✅
SSH connection              ✅
Linux detection             ✅
Shell detection             ✅
Generic command execution   ✅
.tst parser                 ✅
Action registry             ✅
Test executor               ✅

GET_HOSTNAME                ✅
GET_IP_ADDRESS              ✅
GET_OS                      ✅
GET_KERNEL                  ✅
GET_ARCHITECTURE            ✅
GET_MEMORY                  ✅

Planned next:

Central timestamped logging
BoardActions consolidation
Serial connection
USB validation DSL APIs
Project run reporting

16. Quick Start

For the existing Raspberry Pi 5 project:

cd ~/workdir/embite_mvp

source .venv/bin/activate

cat projects/raspberry_pi5/config/project.yaml

cat projects/raspberry_pi5/tests/system.tst

python -m src.embite projects/raspberry_pi5

For RK3588:

cd ~/workdir/embite_mvp

source .venv/bin/activate

cat projects/rk3588/config/project.yaml

python -m src.embite projects/rk3588

17. EmbITE Project Model

The current model can be summarized as:

Project
   │
   ├── project.yaml
   │      ├── Project information
   │      ├── DUT information
   │      ├── Connection information
   │      └── Selected .tst files
   │
   └── tests/
          ├── system.tst
          ├── USB.tst
          ├── PCIE.tst
          └── ...
                 │
                 ▼
              EmbITE
                 │
                 ▼
          DSL Execution
                 │
                 ▼
                DUT

The project configuration decides which tests run.

The .tst files decide which DSL actions execute.

EmbITE decides how those DSL actions are implemented on the DUT.
