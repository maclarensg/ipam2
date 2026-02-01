#!/usr/bin/env python3
"""
🏢 Enterprise IPAM CLI v2.0
- Name-based unique identifiers (no UUIDs)
- Hierarchical: AddressPool -> Pool -> Subnet
- Overlap prevention with proper allocator
"""

import click
import yaml
import sqlalchemy
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import IntegrityError
from models import Base, AddressPool, Vpc, Pool, Subnet
from allocator import AddressPoolAllocator, PoolAllocator
from datetime import datetime
import shutil
import ipaddress
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import box

console = Console()
db = None


class IPAMDatabase:
    def __init__(self, config_file="config.yaml"):
        with open(config_file) as f:
            config = yaml.safe_load(f)["database"]

        self.config = config
        url = config.get("sqlite_url") or config.get("postgres_url")
        self.engine = sqlalchemy.create_engine(url)
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)

        # Caches: keyed by name
        self._addr_pool_allocators = {}  # AddressPool name -> AddressPoolAllocator
        self._pool_allocators = {}  # Pool name -> PoolAllocator

    def session(self):
        return self.Session()

    def get_addr_pool_allocator(self, addr_pool_name: str) -> AddressPoolAllocator:
        """
        Get or create allocator for an AddressPool.
        ALWAYS rebuilds fresh to include ALL existing pools.
        """
        with self.session() as session:
            addr_pool = (
                session.query(AddressPool).filter_by(name=addr_pool_name).first()
            )
            if not addr_pool:
                return None

            # Create fresh allocator with ALL existing pools
            allocator = AddressPoolAllocator(addr_pool.cidr)

            # Add all existing pools in this address pool
            for pool in addr_pool.pools:
                allocator.add_used_range(pool.cidr)

            return allocator

    def get_pool_allocator(self, pool_name: str) -> PoolAllocator:
        """
        Get or create allocator for a Pool.
        ALWAYS rebuilds fresh to include ALL existing subnets.
        """
        with self.session() as session:
            pool = session.query(Pool).filter_by(name=pool_name).first()
            if not pool:
                return None

            # Create fresh allocator with ALL existing subnets
            allocator = PoolAllocator(pool.cidr)

            # Add all existing subnets in this pool
            for subnet in pool.subnets:
                allocator.add_used_range(subnet.cidr)

            return allocator

    def allocate_pool(self, addr_pool_name: str, prefix_length: int) -> Optional[str]:
        """Allocate a new pool from an address pool"""
        allocator = self.get_addr_pool_allocator(addr_pool_name)
        if not allocator:
            return None

        cidr = allocator.find_best_fit(prefix_length)
        return cidr

    def allocate_subnet(self, pool_name: str, prefix_length: int) -> Optional[str]:
        """Allocate a new subnet from a pool"""
        allocator = self.get_pool_allocator(pool_name)
        if not allocator:
            return None

        cidr = allocator.find_best_fit(prefix_length)
        return cidr

    def is_pool_available(self, addr_pool_name: str, cidr: str) -> bool:
        """Check if a CIDR is available in an address pool"""
        allocator = self.get_addr_pool_allocator(addr_pool_name)
        if not allocator:
            return False
        return allocator.is_available(cidr)

    def is_subnet_available(self, pool_name: str, cidr: str) -> bool:
        """Check if a CIDR is available in a pool"""
        allocator = self.get_pool_allocator(pool_name)
        if not allocator:
            return False
        return allocator.is_available(cidr)


db = IPAMDatabase()


@click.group(context_settings={"help_option_names": ["-h", "--help"]})
@click.version_option("2.0", "--version", "-v")
def cli():
    """🏢 Enterprise IPAM CLI v2.0

    Name-based IDs | Hierarchical | No Overlaps
    AddressPool (/8-/16) → Pool (/22-/30) → Subnet (/24-/32)
    """


@cli.command()
def quickstart():
    """🚀 Quickstart guide"""
    click.echo("""
1️⃣  ./ipam2.py addresspool create main 10.0.0.0/16
2️⃣  ./ipam2.py vpc create prod
3️⃣  ./ipam2.py pool create web main prod --prefix 24
4️⃣  ./ipam2.py subnet create frontend web prod --prefix 27
5️⃣  ./ipam2.py subnet create backend web prod --prefix 27
6️⃣  ./ipam2.py report tui
    """)


# ============ ADDRESS POOLS ============


@cli.group()
def addresspool():
    """🏛️ Address Pools (/8-/16) - Top-level supernets"""
    pass


@addresspool.command()
@click.argument("name")
@click.argument("cidr")
def create(name, cidr):
    """Create a new address pool"""
    # Validate CIDR
    try:
        network = ipaddress.IPv4Network(cidr, strict=False)
        if network.prefixlen > 16:
            click.echo(f"❌ CIDR prefix must be /16 or smaller (e.g., /8, /12, /16)")
            return
    except ValueError as e:
        click.echo(f"❌ Invalid CIDR: {e}")
        return

    with db.session() as session:
        try:
            pool = AddressPool(name=name, cidr=cidr)
            session.add(pool)
            session.commit()
            click.echo(f"✅ Created AddressPool: {name} | {cidr}")
        except IntegrityError:
            session.rollback()
            click.echo(f"❌ AddressPool '{name}' already exists")


@addresspool.command(name="list")
def list_pools():
    """List all address pools"""
    with db.session() as session:
        pools = session.query(AddressPool).all()
        if not pools:
            click.echo("No address pools found.")
            return

        table = Table("Name", "CIDR", "#Pools", box=box.ROUNDED)
        for ap in pools:
            count = session.query(Pool).filter_by(address_pool_id=ap.name).count()
            table.add_row(ap.name, ap.cidr, str(count))
        console.print(table)


@addresspool.command()
@click.argument("name")
def delete(name):
    """Delete an address pool (and all its pools)"""
    with db.session() as session:
        pool = session.query(AddressPool).filter_by(name=name).first()
        if not pool:
            click.echo(f"❌ AddressPool '{name}' not found")
            return

        # Check for existing pools
        pool_count = session.query(Pool).filter_by(address_pool_id=name).count()
        if pool_count > 0:
            click.echo(
                f"❌ Cannot delete: {pool_count} pools exist in this address pool"
            )
            return

        session.delete(pool)
        session.commit()
        click.echo(f"✅ Deleted AddressPool: {name}")


# ============ VPCS ============


@cli.group()
def vpc():
    """🌐 VPCs - Logical groupings"""
    pass


@vpc.command()
@click.argument("name")
def create(name):
    """Create a new VPC"""
    with db.session() as session:
        try:
            vpc = Vpc(name=name)
            session.add(vpc)
            session.commit()
            click.echo(f"✅ Created VPC: {name}")
        except IntegrityError:
            session.rollback()
            click.echo(f"❌ VPC '{name}' already exists")


@vpc.command(name="list")
def list_vpcs():
    """List all VPCs"""
    with db.session() as session:
        vpcs = session.query(Vpc).all()
        if not vpcs:
            click.echo("No VPCs found.")
            return

        table = Table("Name", "#Pools", "#Subnets", box=box.ROUNDED)
        for v in vpcs:
            pool_count = session.query(Pool).filter_by(vpc_id=v.name).count()
            subnet_count = session.query(Subnet).filter_by(vpc_id=v.name).count()
            table.add_row(v.name, str(pool_count), str(subnet_count))
        console.print(table)


@vpc.command()
@click.argument("name")
def delete(name):
    """Delete a VPC (and all its pools/subnets)"""
    with db.session() as session:
        vpc = session.query(Vpc).filter_by(name=name).first()
        if not vpc:
            click.echo(f"❌ VPC '{name}' not found")
            return

        session.delete(vpc)
        session.commit()
        click.echo(f"✅ Deleted VPC: {name}")


# ============ POOLS ============


@cli.group()
def pool():
    """📦 Pools (/22-/30) - Children of AddressPool"""
    pass


@pool.command()
@click.argument("name")
@click.argument("address_pool_name")
@click.argument("vpc_name")
@click.option("--prefix", "-p", default=24, help="CIDR prefix (/22-/30)")
def create(name, address_pool_name, vpc_name, prefix):
    """Create a new pool within an address pool and VPC"""
    # Validate prefix
    if prefix < 22 or prefix > 30:
        click.echo(f"❌ Pool prefix must be /22-/30")
        return

    with db.session() as session:
        # Check if address pool exists
        addr_pool = session.query(AddressPool).filter_by(name=address_pool_name).first()
        if not addr_pool:
            click.echo(f"❌ AddressPool '{address_pool_name}' not found")
            return

        # Check if VPC exists
        vpc = session.query(Vpc).filter_by(name=vpc_name).first()
        if not vpc:
            click.echo(f"❌ VPC '{vpc_name}' not found")
            return

        # Check if pool name already exists in this address pool
        existing = (
            session.query(Pool)
            .filter_by(address_pool_id=address_pool_name, name=name)
            .first()
        )
        if existing:
            click.echo(
                f"❌ Pool '{name}' already exists in AddressPool '{address_pool_name}'"
            )
            return

        # Allocate from address pool
        cidr = db.allocate_pool(address_pool_name, prefix)

        if not cidr:
            click.echo(f"❌ No space available in {address_pool_name}")
            return

        try:
            pool = Pool(
                name=name, cidr=cidr, address_pool_id=address_pool_name, vpc_id=vpc_name
            )
            session.add(pool)
            session.commit()
            click.echo(f"✅ Created Pool: {name} | {cidr}")
        except IntegrityError:
            session.rollback()
            click.echo(f"❌ Pool '{name}' already exists")


@pool.command(name="list")
def list_pools():
    """List all pools"""
    with db.session() as session:
        pools = session.query(Pool).all()
        if not pools:
            click.echo("No pools found.")
            return

        table = Table("Name", "CIDR", "AddressPool", "VPC", "#Subnets", box=box.ROUNDED)
        for p in pools:
            subnet_count = session.query(Subnet).filter_by(pool_id=p.id).count()
            table.add_row(
                p.name, p.cidr, p.address_pool_id, p.vpc_id, str(subnet_count)
            )
        console.print(table)


@pool.command()
@click.argument("name")
def delete(name):
    """Delete a pool (and all its subnets)"""
    with db.session() as session:
        pool = session.query(Pool).filter_by(name=name).first()
        if not pool:
            click.echo(f"❌ Pool '{name}' not found")
            return

        session.delete(pool)
        session.commit()
        click.echo(f"✅ Deleted Pool: {name}")


# ============ SUBNETS ============


@cli.group()
def subnet():
    """🔢 Subnets (/24-/32) - Children of Pool"""
    pass


@subnet.command()
@click.argument("name")
@click.argument("pool_name")
@click.argument("vpc_name")
@click.option("--prefix", "-p", default=27, help="CIDR prefix (/24-/32)")
def create(name, pool_name, vpc_name, prefix):
    """Create a new subnet within a pool and VPC"""
    # Validate prefix
    if prefix < 24 or prefix > 32:
        click.echo(f"❌ Subnet prefix must be /24-/32")
        return

    with db.session() as session:
        # Check if pool exists
        pool = session.query(Pool).filter_by(name=pool_name).first()
        if not pool:
            click.echo(f"❌ Pool '{pool_name}' not found")
            return

        # Check if VPC exists
        vpc = session.query(Vpc).filter_by(name=vpc_name).first()
        if not vpc:
            click.echo(f"❌ VPC '{vpc_name}' not found")
            return

        # Verify VPC matches pool's VPC
        if pool.vpc_id != vpc_name:
            click.echo(
                f"❌ VPC mismatch: Pool belongs to '{pool.vpc_id}', not '{vpc_name}'"
            )
            return

        # Check if subnet name already exists in this pool
        existing = session.query(Subnet).filter_by(pool_id=pool.id, name=name).first()
        if existing:
            click.echo(f"❌ Subnet '{name}' already exists in Pool '{pool_name}'")
            return

        # Allocate from pool
        cidr = db.allocate_subnet(pool_name, prefix)

        if not cidr:
            click.echo(f"❌ No space available in {pool_name}")
            return

        try:
            subnet = Subnet(name=name, cidr=cidr, pool_id=pool.id, vpc_id=vpc_name)
            session.add(subnet)
            session.commit()
            click.echo(f"✅ Created Subnet: {name} | {cidr}")
        except IntegrityError:
            session.rollback()
            click.echo(f"❌ Subnet '{name}' already exists")


@subnet.command(name="list")
def list_subnets():
    """List all subnets"""
    with db.session() as session:
        subnets = session.query(Subnet).all()
        if not subnets:
            click.echo("No subnets found.")
            return

        table = Table("Name", "CIDR", "Pool", "VPC", box=box.ROUNDED)
        for s in subnets:
            table.add_row(s.name, s.cidr, s.pool.name if s.pool else "?", s.vpc_id)
        console.print(table)


@subnet.command()
@click.argument("name")
def delete(name):
    """Delete a subnet"""
    with db.session() as session:
        subnet = session.query(Subnet).filter_by(name=name).first()
        if not subnet:
            click.echo(f"❌ Subnet '{name}' not found")
            return

        session.delete(subnet)
        session.commit()
        click.echo(f"✅ Deleted Subnet: {name}")


# ============ REPORTS ============


@cli.group()
def report():
    """📊 Reports"""
    pass


@report.command()
def tui():
    """Show utilization report"""
    with db.session() as session:
        aps = session.query(AddressPool).all()
        console.print(Panel("🏢 IPAM Utilization Report", style="bold cyan"))

        for ap in aps:
            # Calculate AddressPool utilization
            network = ipaddress.IPv4Network(ap.cidr, strict=False)
            total_slots = 2 ** (24 - network.prefixlen)  # e.g., /16 -> 2^8 = 256 slots

            pools = session.query(Pool).filter_by(address_pool_id=ap.name).all()
            pool_count = len(pools)
            util = (pool_count / total_slots) * 100 if total_slots > 0 else 0
            bar = "█" * min(int(util / 5), 20) + "░" * max(20 - int(util / 5), 0)

            console.print(f"\n📦 AddressPool: {ap.name} ({ap.cidr})")
            console.print(
                f"   Utilization: {pool_count}/{total_slots} pools {bar} {util:.1f}%"
            )

            # Group pools by VPC
            vpc_pools = {}
            for p in pools:
                if p.vpc_id not in vpc_pools:
                    vpc_pools[p.vpc_id] = []
                vpc_pools[p.vpc_id].append(p)

            # Show each VPC
            for vpc_name, vpc_pools_list in vpc_pools.items():
                vpc_subnet_count = sum(
                    session.query(Subnet).filter_by(pool_id=p.id).count()
                    for p in vpc_pools_list
                )
                console.print(f"\n   🌐 VPC: {vpc_name}")
                console.print(
                    f"      Pools: {len(vpc_pools_list)} | Subnets: {vpc_subnet_count}"
                )

                # Show pools in this VPC
                for i, p in enumerate(vpc_pools_list):
                    net = ipaddress.IPv4Network(p.cidr, strict=False)
                    pool_size = net.num_addresses
                    subnets = session.query(Subnet).filter_by(pool_id=p.id).all()
                    subnet_count = len(subnets)
                    used_ips = sum(
                        ipaddress.IPv4Network(s.cidr, strict=False).num_addresses
                        for s in subnets
                    )
                    util_percent = (used_ips / pool_size) * 100 if pool_size > 0 else 0
                    pool_bar = "█" * min(int(util_percent / 5), 20) + "░" * max(
                        20 - int(util_percent / 5), 0
                    )

                    # Tree characters
                    is_last_pool = i == len(vpc_pools_list) - 1
                    pool_prefix = "   └──" if is_last_pool else "   ├──"
                    pool_connector = "       " if is_last_pool else "   │   "

                    console.print(f"{pool_prefix} 📦 {p.name} ({p.cidr})")
                    console.print(
                        f"{pool_connector}    Used: {used_ips}/{pool_size} IPs {pool_bar} {util_percent:.1f}%"
                    )

                    # Show subnets in this pool
                    for j, s in enumerate(subnets):
                        is_last_subnet = j == len(subnets) - 1
                        subnet_prefix = pool_connector + (
                            "   └──" if is_last_subnet else "   ├──"
                        )
                        console.print(f"{subnet_prefix} 🔢 {s.name} ({s.cidr})")

            if not pools:
                console.print("   (no pools)")


# ============ BACKUP ============


@cli.group()
def backup():
    """💾 Backup"""
    pass


@backup.command()
def create():
    """Create a timestamped backup"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = f"ipam_{timestamp}.db"

    # Find the actual database file
    with open("config.yaml") as f:
        config = yaml.safe_load(f)["database"]
    db_url = config.get("sqlite_url") or config.get("postgres_url")

    if db_url.startswith("sqlite:///"):
        db_file = db_url.replace("sqlite:///", "")
        if db_file and db_file != ":memory:":
            shutil.copy(db_file, backup_file)
            click.echo(f"✅ Backup: {backup_file}")
            return

    # For other databases or memory, skip backup
    click.echo("⚠️  Backup not supported for this database type")


if __name__ == "__main__":
    cli()
