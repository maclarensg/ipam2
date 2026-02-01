"""
IP Allocator - Best-Fit with Overlap Prevention
Handles hierarchical: AddressPool -> Pool -> Subnet
"""

import ipaddress
from typing import List, Optional, Tuple
import bisect


class IPAllocator:
    """Base allocator for hierarchical IP space management"""

    def __init__(self, parent_cidr: str):
        self.parent_cidr = parent_cidr
        self.parent_network = ipaddress.IPv4Network(parent_cidr, strict=False)
        self.used_ranges: List[Tuple[int, int]] = []

    def _ip_to_int(self, ip: str) -> int:
        return int(ipaddress.IPv4Address(ip))

    def _int_to_ip(self, ip_int: int) -> str:
        return str(ipaddress.IPv4Address(ip_int))

    def _network_range(self, cidr: str) -> Tuple[int, int]:
        """Get (start, end) integer range for a CIDR"""
        network = ipaddress.IPv4Network(cidr, strict=False)
        return (
            self._ip_to_int(str(network.network_address)),
            self._ip_to_int(str(network.broadcast_address)),
        )

    def add_used_range(self, cidr: str):
        """Add an allocated CIDR to used ranges"""
        start, end = self._network_range(cidr)
        bisect.insort(self.used_ranges, (start, end))
        self._merge_ranges()

    def _merge_ranges(self):
        """Merge overlapping/adjacent ranges"""
        if not self.used_ranges:
            return

        merged = []
        for start, end in sorted(self.used_ranges):
            if not merged:
                merged.append([start, end])
            elif merged[-1][1] + 1 >= start:  # Overlap or adjacent
                merged[-1][1] = max(merged[-1][1], end)
            else:
                merged.append([start, end])
        self.used_ranges = [(s[0], s[1]) for s in merged]

    def is_available(self, cidr: str) -> bool:
        """Check if a CIDR is available (not overlapping)"""
        start, end = self._network_range(cidr)

        for used_start, used_end in self.used_ranges:
            # Check for any overlap
            if not (end < used_start or start > used_end):
                return False
        return True

    def find_best_fit(self, prefix_length: int) -> Optional[str]:
        """
        Find the best-fit CIDR for the given prefix length.
        Allocates from the center of the largest available gap.
        """
        required_size = 2 ** (32 - prefix_length)
        parent_start = self._ip_to_int(str(self.parent_network.network_address))
        parent_end = self._ip_to_int(str(self.parent_network.broadcast_address))

        gaps: List[Tuple[int, int, float]] = []

        # If no used ranges, entire parent is available
        if not self.used_ranges:
            gap_start = parent_start
            gap_end = parent_end
            if gap_end - gap_start + 1 >= required_size:
                gaps.append(
                    (gap_start, gap_end, abs(gap_end - gap_start + 1 - required_size))
                )
        else:
            # Gap before first range
            if self.used_ranges[0][0] > parent_start + required_size - 1:
                gap_start = parent_start
                gap_end = min(parent_end, self.used_ranges[0][0] - 1)
                if gap_end - gap_start + 1 >= required_size:
                    gaps.append(
                        (
                            gap_start,
                            gap_end,
                            abs(gap_end - gap_start + 1 - required_size),
                        )
                    )

            # Gaps between ranges
            for i in range(len(self.used_ranges) - 1):
                gap_start = self.used_ranges[i][1] + 1
                gap_end = self.used_ranges[i + 1][0] - 1
                if gap_end - gap_start + 1 >= required_size:
                    gaps.append(
                        (
                            gap_start,
                            gap_end,
                            abs(gap_end - gap_start + 1 - required_size),
                        )
                    )

            # Gap after last range
            if self.used_ranges[-1][1] < parent_end - required_size + 1:
                gap_start = self.used_ranges[-1][1] + 1
                gap_end = parent_end
                if gap_end - gap_start + 1 >= required_size:
                    gaps.append(
                        (
                            gap_start,
                            gap_end,
                            abs(gap_end - gap_start + 1 - required_size),
                        )
                    )

        if not gaps:
            return None

        # Find best gap (smallest waste = closest to required size)
        best_gap = min(gaps, key=lambda x: x[2])
        gap_start, gap_end, _ = best_gap
        gap_size = gap_end - gap_start + 1

        # Calculate allocation start, aligned to network boundary
        mask = (0xFFFFFFFF << (32 - prefix_length)) & 0xFFFFFFFF

        # Center of gap
        gap_center = gap_start + (gap_size // 2)

        # Align to network boundary
        alloc_start = gap_center & mask

        # Ensure it's within the gap and has enough space
        if alloc_start < gap_start:
            alloc_start = ((gap_start >> (32 - prefix_length)) + 1) << (
                32 - prefix_length
            )

        alloc_end = alloc_start + required_size - 1
        if alloc_end > gap_end:
            alloc_start = ((gap_end - required_size + 1) >> (32 - prefix_length)) << (
                32 - prefix_length
            )
            alloc_end = alloc_start + required_size - 1

        # Final validation
        if alloc_start < gap_start or alloc_end > gap_end:
            return None

        alloc_cidr = f"{self._int_to_ip(alloc_start)}/{prefix_length}"

        self.add_used_range(alloc_cidr)
        return alloc_cidr


class AddressPoolAllocator(IPAllocator):
    """
    Allocates Pools within an AddressPool.
    Keyed by AddressPool name (not pool name).
    """

    pass


class PoolAllocator(IPAllocator):
    """
    Allocates Subnets within a Pool.
    Keyed by Pool name (not subnet name).
    """

    pass
