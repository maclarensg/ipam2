# IPAM2 - Enterprise IP Address Management

<div align="center">

**🏢 Enterprise IP Address Management CLI with Hierarchical Allocation**

[![CI](https://github.com/maclarensg/ipam2/actions/workflows/ci-pr.yml/badge.svg)](https://github.com/maclarensg/ipam2/actions)
[![Docker](https://img.shields.io/badge/docker-maclarensg%2Fipam2-blue)](https://hub.docker.com/r/maclarensg/ipam2)

</div>

## Features

- **🏛️ Hierarchical Structure**: AddressPool → VPC → Pool → Subnet
- **✅ Non-overlapping Allocation**: Automatic best-fit allocation prevents CIDR conflicts
- **📊 Rich Reports**: Visual utilization reports with progress bars
- **🐳 Container Ready**: Dockerfile and Docker Hub support
- **📦 Standalone Binary**: Build self-contained executable with PyInstaller
- **🔄 Multiple Databases**: SQLite (default) and PostgreSQL support
- **🔧 Task Automation**: Taskfile for common operations
- **🎯 Flexible CIDR**: Any prefix length (/0-/32) with hierarchy enforcement

## Quick Start

### Using Python

```bash
# Install dependencies
pip install -r requirements.txt

# Create address pool
./ipam2.py addresspool create main 10.0.0.0/16

# Create VPC
./ipam2.py vpc create production

# Create pool
./ipam2.py pool create web main production --prefix 24

# Create subnet
./ipam2.py subnet create frontend web production --prefix 27

# Show report
./ipam2.py report tui
```

### Using Docker

```bash
# Pull image
docker pull maclarensg/ipam2:latest

# Run
docker run --rm maclarensg/ipam2:latest --help

# With data persistence
docker run -v $(pwd)/data:/data --rm maclarensg/ipam2:latest report tui
```

### Using Standalone Binary

```bash
# Download from releases (versioned binary)
chmod +x ipam2-v1.0.0
./ipam2-v1.0.0 --help

# Or rename to ipam2 for convenience
mv ipam2-v1.0.0 ipam2
./ipam2 --help
```

**Binary Naming**: Releases include versioned binaries (e.g., `ipam2-v1.0.0`, `ipam2-v2.1.3`)

## Installation

### Prerequisites

- Python 3.14+
- SQLite or PostgreSQL

### Clone and Install

```bash
git clone git@github.com:maclarensg/ipam2.git
cd ipam2

# Install dependencies
pip install -r requirements.txt

# Optional: Build standalone binary
task build

# Optional: Build Docker image
task docker-build TAG=latest
```

## Usage

### Command Reference

| Command | Description |
|---------|-------------|
| `./ipam2.py addresspool create <name> <cidr>` | Create address pool (/0-/32) |
| `./ipam2.py vpc create <name>` | Create VPC |
| `./ipam2.py pool create <name> <addr_pool> <vpc> [--prefix]` | Create pool (/0-/32, smaller than AddressPool) |
| `./ipam2.py subnet create <name> <pool> <vpc> [--prefix]` | Create subnet (/0-/32, smaller than Pool) |
| `./ipam2.py addresspool list` | List address pools |
| `./ipam2.py vpc list` | List VPCs |
| `./ipam2.py pool list` | List pools |
| `./ipam2.py subnet list` | List subnets |
| `./ipam2.py report tui` | Show utilization report |
| `./ipam2.py backup create` | Create database backup |

### Example: Multi-Project Setup

```bash
# Create address pools
./ipam2.py addresspool create prod-net 10.0.0.0/16
./ipam2.py addresspool create stag-net 10.1.0.0/16

# Create VPCs
./ipam2.py vpc create Project1
./ipam2.py vpc create Project2

# Create pools (PRD from prod-net, NON-PRD from stag-net)
./ipam2.py pool create prd-pool prod-net Project1 --prefix 24
./ipam2.py pool create nonprd-pool stag-net Project1 --prefix 24
./ipam2.py pool create prd-pool-p2 prod-net Project2 --prefix 24
./ipam2.py pool create nonprd-pool-p2 stag-net Project2 --prefix 24

# Create subnets
./ipam2.py subnet create p1-prd-api prd-pool Project1 --prefix 28
./ipam2.py subnet create p1-sit-api nonprd-pool Project1 --prefix 28
./ipam2.py subnet create p1-uat-api nonprd-pool Project1 --prefix 28

# Show report
./ipam2.py report tui
```

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    AddressPool: prod-net (10.0.0.0/16)      │
│                         Utilization: 0.8%                    │
├─────────────────────────────────────────────────────────────┤
│  VPC: Project1                                               │
│  └── prd-pool (10.0.128.0/24) - 18.8% used                  │
│      ├── p1-prd-api (10.0.128.128/28)                       │
│      ├── p1-prd-web (10.0.128.192/28)                       │
│      └── p1-prd-db (10.0.128.160/28)                        │
└─────────────────────────────────────────────────────────────┘
```

### Hierarchy

| Level | Constraint | Example |
|-------|------------|---------|
| AddressPool | /0 - /32 | 10.0.0.0/16 |
| Pool | /0 - /32, must be smaller than AddressPool | 10.0.128.0/24 |
| Subnet | /0 - /32, must be smaller than Pool | 10.0.128.128/28 |

**Note**: A smaller prefix means a larger network (e.g., /16 is smaller than /24). Pool/Subnet prefix length must be **greater than** parent prefix length.

## Configuration

### Standalone Binary (Recommended)

For the standalone binary, config and database are stored in XDG standard location:

```bash
# Config file
~/.config/ipam2/config.yaml

# SQLite database
~/.config/ipam2/ipam.db
```

The config file is automatically created with defaults on first run.

### Python Script

For Python script usage, config is loaded from:

1. `./config.yaml` (legacy, current directory)
2. `~/.config/ipam2/config.yaml` (XDG standard)

Edit `config.yaml` to change database:

```yaml
database:
  driver: sqlite  # sqlite or postgresql
  sqlite_url: "sqlite:///ipam.db"
  # postgres_url: "postgresql://user:password@localhost:5432/ipam"
```

### Environment Variables

- `XDG_CONFIG_HOME`: Override default config directory (default: `~/.config`)

## Task Automation

```bash
# Install dependencies
task install

# Run tests
task test

# Build binary
task build

# Build and push Docker
task docker-login
task docker-release TAG=v2.0.0

# Full release
task release TAG=v2.0.0

# Show help
task help
```

## Development

```bash
# Install dev dependencies
task install-dev

# Run linter
task lint

# Format code
task format

# Clean up
task reset
```

## CI/CD

### Pull Requests

- Linting (ruff + black)
- Functional tests
- Security scanning (bandit + safety)
- Docker build verification

### Releases

Triggered on `v*` tags:

1. Runs lint + tests
2. Builds standalone binary
3. Builds Docker image
4. Pushes to Docker Hub
5. Creates GitHub release with binary

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make changes
4. Run tests: `task test`
5. Submit PR

## Security

For security vulnerabilities, please contact directly.

## License

MIT License - see LICENSE file for details.

## Author

**Gavin Yap** - [maclarensg@gmail.com](mailto:maclarensg@gmail.com)

---

<div align="center">

**IPAM2** - Enterprise IP Address Management Made Simple

</div>
