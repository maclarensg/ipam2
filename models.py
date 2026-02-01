"""
SQLAlchemy ORM Models for IPAM
Using name as unique identifier (no UUIDs)
"""

from sqlalchemy import Column, String, Integer, ForeignKey, Text, UniqueConstraint
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
import ipaddress

Base = declarative_base()


class AddressPool(Base):
    """Top-level address pool (/8 to /16) - e.g., 10.0.0.0/16"""

    __tablename__ = "address_pools"

    name = Column(String(100), primary_key=True)
    cidr = Column(String(18), nullable=False)

    # Relationships
    pools = relationship(
        "Pool", back_populates="address_pool", cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<AddressPool {self.name}: {self.cidr}>"

    @property
    def network(self):
        return ipaddress.IPv4Network(self.cidr, strict=False)

    def contains(self, cidr):
        """Check if a CIDR is within this pool"""
        return ipaddress.IPv4Network(cidr, strict=False).subnet_of(self.network)


class Vpc(Base):
    """Virtual Private Cloud - logical grouping"""

    __tablename__ = "vpcs"

    name = Column(String(100), primary_key=True)

    # Relationships
    pools = relationship("Pool", back_populates="vpc", cascade="all, delete-orphan")
    subnets = relationship("Subnet", back_populates="vpc", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Vpc {self.name}>"


class Pool(Base):
    """Mid-level pool (/22 to /30) - child of AddressPool"""

    __tablename__ = "pools"
    __table_args__ = (
        UniqueConstraint("address_pool_id", "name", name="uq_pool_address_pool_name"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False)
    cidr = Column(String(18), nullable=False)

    # Foreign keys
    address_pool_id = Column(
        String(100), ForeignKey("address_pools.name"), nullable=False
    )
    vpc_id = Column(String(100), ForeignKey("vpcs.name"), nullable=False)

    # Relationships
    address_pool = relationship("AddressPool", back_populates="pools")
    vpc = relationship("Vpc", back_populates="pools")
    subnets = relationship(
        "Subnet", back_populates="pool", cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<Pool {self.name}: {self.cidr}>"

    @property
    def network(self):
        return ipaddress.IPv4Network(self.cidr, strict=False)

    def contains(self, cidr):
        """Check if a CIDR is within this pool"""
        return ipaddress.IPv4Network(cidr, strict=False).subnet_of(self.network)


class Subnet(Base):
    """Leaf-level subnet (/24 to /32) - child of Pool"""

    __tablename__ = "subnets"
    __table_args__ = (UniqueConstraint("pool_id", "name", name="uq_subnet_pool_name"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False)
    cidr = Column(String(18), nullable=False)

    # Foreign keys
    pool_id = Column(Integer, ForeignKey("pools.id"), nullable=False)
    vpc_id = Column(String(100), ForeignKey("vpcs.name"), nullable=False)

    # Relationships
    pool = relationship("Pool", back_populates="subnets")
    vpc = relationship("Vpc", back_populates="subnets")

    def __repr__(self):
        return f"<Subnet {self.name}: {self.cidr}>"

    @property
    def network(self):
        return ipaddress.IPv4Network(self.cidr, strict=False)

    def contains(self, cidr):
        """Check if a CIDR is within this subnet"""
        return ipaddress.IPv4Network(cidr, strict=False).subnet_of(self.network)
