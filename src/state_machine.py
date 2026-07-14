"""
贾维斯 v2 状态机

状态流转：
  STANDBY → (唤醒词) → AWAKE_LISTENING → (ASR 完成) → PROCESSING
    → (快速动作) → SPEAKING → AWAKE_LISTENING
    → (Claude 回复) → SPEAKING → AWAKE_LISTENING
    → (超时) → STANDBY

子状态 (interaction_status)：仅作 UI 提示用，不影响主状态流转
  idle / listening / thinking / speaking / executing_tool
"""

from __future__ import annotations

import enum
import time
import logging

logger = logging.getLogger(__name__)


class MainState(enum.Enum):
    STANDBY = "standby"
    AWAKE_LISTENING = "awake_listening"
    PROCESSING = "processing"
    SPEAKING = "speaking"


class InteractionStatus(enum.Enum):
    IDLE = "idle"
    LISTENING = "listening"
    THINKING = "thinking"
    SPEAKING = "speaking"
    EXECUTING_TOOL = "executing_tool"


class StateMachine:
    """核心状态机，管理唤醒/待机/处理/说话四个主状态。"""

    def __init__(self):
        self._state = MainState.STANDBY
        self._interaction = InteractionStatus.IDLE
        self._last_activity = time.time()
        self._idle_timeout = 30  # 秒
        self._active_role = "jarvis"

        # 回调
        self.on_state_change = None   # callable(MainState)
        self.on_interaction_change = None  # callable(InteractionStatus)
        self._listeners = []

    # ── 属性 ──────────────────────────────────────────────

    @property
    def state(self) -> MainState:
        return self._state

    @property
    def interaction_status(self) -> InteractionStatus:
        return self._interaction

    @property
    def active_role(self) -> str:
        return self._active_role

    @property
    def is_standby(self) -> bool:
        return self._state == MainState.STANDBY

    @property
    def is_awake(self) -> bool:
        return self._state != MainState.STANDBY

    # ── 状态转换 ──────────────────────────────────────────

    def wake(self, role: str = "jarvis"):
        """唤醒：从 STANDBY → AWAKE_LISTENING"""
        if self._state == MainState.STANDBY:
            self._active_role = role
            self._transition(MainState.AWAKE_LISTENING)
            self.interaction = InteractionStatus.LISTENING
            self._last_activity = time.time()
            logger.info(f"🔊 唤醒：{role}")

    def standby(self, reason: str = "manual"):
        """进入待机"""
        if self._state != MainState.STANDBY:
            self._transition(MainState.STANDBY)
            self.interaction = InteractionStatus.IDLE
            logger.info(f"🛏️ 待机 ({reason})")

    def start_processing(self):
        """开始处理用户指令"""
        self._transition(MainState.PROCESSING)
        self.interaction = InteractionStatus.THINKING
        self._last_activity = time.time()

    def start_speaking(self):
        """开始 TTS 播报"""
        self._transition(MainState.SPEAKING)
        self.interaction = InteractionStatus.SPEAKING

    def finish_speaking(self):
        """TTS 结束，回到监听"""
        self._transition(MainState.AWAKE_LISTENING)
        self.interaction = InteractionStatus.LISTENING
        self._last_activity = time.time()

    def user_left(self):
        """用户离开/不再交互"""
        self.standby(reason="user_left")

    # ── 交互子状态 ────────────────────────────────────────

    @property
    def interaction(self) -> InteractionStatus:
        return self._interaction

    @interaction.setter
    def interaction(self, status: InteractionStatus):
        if self._interaction != status:
            self._interaction = status
            if self.on_interaction_change:
                try:
                    self.on_interaction_change(status)
                except Exception:
                    pass

    # ── 超时检查 ──────────────────────────────────────────

    def check_idle_timeout(self) -> bool:
        """检查是否因无活动而应返回待机。返回 True 表示已超时并已自动待机。"""
        if self._state == MainState.STANDBY:
            return False
        idle_seconds = time.time() - self._last_activity
        if idle_seconds > self._idle_timeout:
            self.standby(reason=f"idle_{idle_seconds:.0f}s")
            return True
        return False

    def touch(self):
        """更新最后活动时间"""
        self._last_activity = time.time()

    # ── 内部 ──────────────────────────────────────────────

    def _transition(self, new_state: MainState):
        old = self._state
        self._state = new_state
        if self.on_state_change and old != new_state:
            try:
                self.on_state_change(new_state)
            except Exception:
                pass


# 全局单例
_state_machine: StateMachine | None = None


def get_state_machine() -> StateMachine:
    global _state_machine
    if _state_machine is None:
        _state_machine = StateMachine()
    return _state_machine
