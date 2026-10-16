"""Arm 抽象。**所有 arm 必须通过同一个入口、同样的调用预算口径、同样记录真实调用数。**"""
from __future__ import annotations
from typing import Protocol
from dataclasses import dataclass, field


@dataclass
class ArmResult:
    arm: str
    topic_id: str
    rep: int
    text: str
    branches: int = 0
    notes: dict = field(default_factory=dict)


class Arm(Protocol):
    name: str

    def run(self, llm, topic: dict, rep: int) -> ArmResult: ...
