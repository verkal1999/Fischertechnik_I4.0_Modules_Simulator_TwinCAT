from __future__ import annotations

from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from pathlib import Path
import threading
import time
from typing import Any, Dict, Iterator, List, Mapping, Optional, Sequence, Tuple

import pyads
from opcua import Client, ua


PROJECT_DIR = Path(__file__).resolve().parent
CERT_DIR = PROJECT_DIR / "certs"


DEFAULT_HRL_SKILLSET_NODEID = "ns=4;s=HRL_SkillSet"
DEFAULT_HRL_AUSLAGERN_METHOD_NODEID = (
    "ns=4;s=HRL_SkillSet.HRL_NMethod_Auslagern.HRL_NMethod_Auslagern"
)
DEFAULT_VSG_COMPRESSOR_METHOD_NODEID = (
    "ns=4;s=VSG_SkillSet.VSG_Skill_SuctionProcess.JobMethode_CompressorControl"
)


DEFAULT_BOOL_SYMBOLS: Dict[str, str] = {
    "notaus_a": "GVL_Sim.diNotAus_Kanal_A",
    "notaus_b": "GVL_Sim.diNotAus_Kanal_B",
    "sim": "GVL_Sim.bSimMode",
    "diag_finished": "OPCUA.Diag_finished",
    "hrl_reset_button": "HRL_SkillSet.ResetButton",
    "hrl_start_button": "HRL_SkillSet.StartButton",
    "hrl_confirmation_button": "HRL_SkillSet.ConfirmationButton",
    "vsg_reset_button": "VSG_SkillSet.ResetButton",
    "vsg_start_button": "VSG_SkillSet.StartButton",
    "vsg_confirmation_button": "VSG_SkillSet.ConfirmationButton",
    "ts_horizontal": "GVL_HRL_Sim.HRL_Ref_Taster_horizontal",
    "ts_vertical": "GVL_HRL_Sim.HRL_Ref_Taster_vertikal",
    "ts_ausleger_vorne": "GVL_HRL_Sim.HRL_Ref_Taster_Ausleger_vorne",
    "ts_ausleger_hinten": "GVL_HRL_Sim.HRL_Ref_Taster_Ausleger_hinten",
    "ls_inner": "GVL_HRL_Sim.HRL_LS_innen",
    "ls_outer": "GVL_HRL_Sim.HRL_LS_aussen",
}


DEFAULT_UDINT_SYMBOLS: Dict[str, str] = {
    "horizontal_1": "GVL_HRL_Sim.HRL_Enc_horizontal_I1",
    "horizontal_2": "GVL_HRL_Sim.HRL_Enc_horizontal_I2",
    "vertical_1": "GVL_HRL_Sim.HRL_Enc_vertikal_I1",
    "vertical_2": "GVL_HRL_Sim.HRL_Enc_vertikal_I2",
    "vsg_rotation_1": "GVL_VSG_Sim.VSG_Enc_drehen_I1",
    "vsg_rotation_2": "GVL_VSG_Sim.VSG_Enc_drehen_I2",
    "vsg_horizontal_1": "GVL_VSG_Sim.VSG_Enc_horizontal_I1",
    "vsg_horizontal_2": "GVL_VSG_Sim.VSG_Enc_horizontal_I2",
    "vsg_vertical_1": "GVL_VSG_Sim.VSG_Enc_vertikal_I1",
    "vsg_vertical_2": "GVL_VSG_Sim.VSG_Enc_vertikal_I2",
}


DEFAULT_STRING_SYMBOLS: Dict[str, str] = {
    "last_executed_skill": "OPCUA.lastExecutedSkill",
    "last_finished_skill": "OPCUA.lastFinishedSkill",
    "last_executed_process": "OPCUA.lastExecutedProcess",
}


BUILTIN_NODEID_TO_VARIANT = {
    1: ua.VariantType.Boolean,
    2: ua.VariantType.SByte,
    3: ua.VariantType.Byte,
    4: ua.VariantType.Int16,
    5: ua.VariantType.UInt16,
    6: ua.VariantType.Int32,
    7: ua.VariantType.UInt32,
    8: ua.VariantType.Int64,
    9: ua.VariantType.UInt64,
    10: ua.VariantType.Float,
    11: ua.VariantType.Double,
    12: ua.VariantType.String,
    13: ua.VariantType.DateTime,
}


class _AsDictMixin:
    def as_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class AdsConnectionConfig(_AsDictMixin):
    ams_net_id: str = "10.1.47.44.1.1"
    port: int = 851


@dataclass(frozen=True)
class OpcUaSecurityConfig(_AsDictMixin):
    use_security: bool = True
    policy: str = "Basic256Sha256"
    mode: str = "SignAndEncrypt"
    client_cert_pem: Path = CERT_DIR / "client_cert.pem"
    client_cert_der: Path = CERT_DIR / "client_cert.der"
    client_key_pem: Path = CERT_DIR / "client_key.pem"

    def build_security_string(self) -> Optional[str]:
        if not self.use_security:
            return None
        return f"{self.policy},{self.mode},{self.client_cert_der},{self.client_key_pem}"

    def validate(self) -> None:
        if not self.use_security:
            return
        missing = [
            path
            for path in (self.client_cert_pem, self.client_cert_der, self.client_key_pem)
            if not path.exists()
        ]
        if missing:
            raise FileNotFoundError(f"Fehlende Zertifikatsdateien: {missing}")


@dataclass(frozen=True)
class OpcUaConnectionConfig(_AsDictMixin):
    endpoint: str = "opc.tcp://DESKTOP-LNJR8E0:4840"
    application_uri: str = "urn:ma:implementierung-sim-ma:python-opcua-client"
    username: Optional[str] = None
    password: Optional[str] = None
    plc_root_name: str = "PLC1"
    skillset_name: str = "HRL_SkillSet"
    skillset_nodeid: Optional[str] = DEFAULT_HRL_SKILLSET_NODEID
    request_timeout_seconds: float = 45.0
    secure_channel_timeout_ms: int = 300000
    session_timeout_ms: int = 300000
    security: OpcUaSecurityConfig = field(default_factory=OpcUaSecurityConfig)


@dataclass(frozen=True)
class MethodReference(_AsDictMixin):
    method_nodeid: Optional[str] = None
    container_name: Optional[str] = None
    method_name: Optional[str] = None

    def validate(self) -> None:
        if self.method_nodeid:
            return
        if self.container_name and self.method_name:
            return
        raise ValueError(
            "MethodReference braucht entweder method_nodeid oder container_name + method_name."
        )


@dataclass(frozen=True)
class MethodArgumentDefinition(_AsDictMixin):
    name: str
    data_type_nodeid: Optional[str]
    variant_type: Optional[str]


@dataclass(frozen=True)
class MethodSignature(_AsDictMixin):
    method_name: str
    method_nodeid: str
    parent_name: str
    parent_nodeid: str
    inputs: Tuple[MethodArgumentDefinition, ...]
    outputs: Tuple[MethodArgumentDefinition, ...]


@dataclass(frozen=True)
class AdsReadResult(_AsDictMixin):
    symbol: str
    value: Any


@dataclass(frozen=True)
class AdsWriteReceipt(_AsDictMixin):
    symbol: str
    value: Any
    delay_seconds: Optional[float] = None
    scheduled: bool = False


@dataclass(frozen=True)
class BoolWriteEvent(_AsDictMixin):
    delay_seconds: float
    symbol_or_key: str
    value: bool


@dataclass(frozen=True)
class UdintWriteEvent(_AsDictMixin):
    delay_seconds: float
    symbol_or_key: str
    value: int


@dataclass(frozen=True)
class SpsStartPlan(_AsDictMixin):
    bool_events: Tuple[BoolWriteEvent, ...] = field(default_factory=tuple)
    udint_events: Tuple[UdintWriteEvent, ...] = field(default_factory=tuple)

    def is_empty(self) -> bool:
        return not self.bool_events and not self.udint_events


@dataclass(frozen=True)
class MethodCallResult(_AsDictMixin):
    method_name: str
    method_nodeid: str
    parent_name: str
    parent_nodeid: str
    status_code: int
    status_code_hex: str
    status_name: str
    status_doc: str
    status_is_good: bool
    status_is_uncertain: bool
    inputs: Dict[str, Any]
    outputs: Dict[str, Any]
    raw_outputs: Tuple[Any, ...]

    def has_error(self) -> bool:
        if "HasError" not in self.outputs:
            return False
        return bool(self.outputs["HasError"])

    def is_done(self) -> bool:
        if "IsDone" not in self.outputs:
            return self.status_is_good or self.status_is_uncertain
        return bool(self.outputs["IsDone"])

    def is_successful(self) -> bool:
        if "HasError" in self.outputs or "IsDone" in self.outputs:
            return self.is_done() and not self.has_error()
        return self.status_is_good or self.status_is_uncertain


@dataclass(frozen=True)
class SkillExecutionResult(_AsDictMixin):
    prepared_signals: Dict[str, bool]
    scheduled_writes: Tuple[AdsWriteReceipt, ...]
    call: MethodCallResult

    def is_successful(self) -> bool:
        return self.call.is_successful()


@dataclass(frozen=True)
class SkillStartPlan(_AsDictMixin):
    name: str
    method: MethodReference
    payload: Dict[str, Any]
    sps_plan: SpsStartPlan = field(default_factory=SpsStartPlan)


@dataclass(frozen=True)
class HrlAuslegerSequenceConfig(_AsDictMixin):
    step30_start_seconds: float = 4.4


@dataclass(frozen=True)
class HrlConveyorSequenceConfig(_AsDictMixin):
    ls_inner_detect_seconds: float = 8.7
    ls_inner_release_seconds: float = 9.2
    ls_outer_detect_seconds: float = 10.0

    def validate(self) -> None:
        if self.ls_inner_release_seconds < self.ls_inner_detect_seconds:
            raise ValueError(
                "ls_inner_release_seconds muss >= ls_inner_detect_seconds sein."
            )
        if self.ls_outer_detect_seconds < self.ls_inner_release_seconds:
            raise ValueError(
                "ls_outer_detect_seconds muss >= ls_inner_release_seconds sein."
            )


@dataclass(frozen=True)
class HrlAuslagernRequest(_AsDictMixin):
    method_call: bool = True
    horizontal_shelf_i1: int = 1000
    horizontal_shelf_i2: int = 1000
    vertical_shelf_i1: int = 500
    vertical_shelf_i2: int = 500
    horizontal_transfer_i1: int = 0
    horizontal_transfer_i2: int = 0
    vertical_transfer_i1: int = 0
    vertical_transfer_i2: int = 0
    timeout_ms: int = 30000

    def to_payload(self) -> Dict[str, Any]:
        return {
            "MethodCall": self.method_call,
            "HorizontalShelf_I1": self.horizontal_shelf_i1,
            "HorizontalShelf_I2": self.horizontal_shelf_i2,
            "VerticalShelf_I1": self.vertical_shelf_i1,
            "VerticalShelf_I2": self.vertical_shelf_i2,
            "HorizontalTransfer_I1": self.horizontal_transfer_i1,
            "HorizontalTransfer_I2": self.horizontal_transfer_i2,
            "VerticalTransfer_I1": self.vertical_transfer_i1,
            "VerticalTransfer_I2": self.vertical_transfer_i2,
            "Timeout": self.timeout_ms,
        }


@dataclass(frozen=True)
class VsgCompressorControlRequest(_AsDictMixin):
    method_call: bool = True
    destination_reached: bool = True
    encoder_target_position_01: int = 100
    encoder_target_position_02: int = 100
    encoder_target_position_03: int = 200
    encoder_target_position_04: int = 200
    encoder_target_position_05: int = 300
    encoder_target_position_06: int = 300

    def to_payload(self) -> Dict[str, Any]:
        return {
            "MethodCall": self.method_call,
            "DestinationReached": self.destination_reached,
            "EncoderTargetPosition_01": self.encoder_target_position_01,
            "EncoderTargetPosition_02": self.encoder_target_position_02,
            "EncoderTargetPosition_03": self.encoder_target_position_03,
            "EncoderTargetPosition_04": self.encoder_target_position_04,
            "EncoderTargetPosition_05": self.encoder_target_position_05,
            "EncoderTargetPosition_06": self.encoder_target_position_06,
        }


class SPS_Simulator:
    def __init__(
        self,
        config: Optional[AdsConnectionConfig] = None,
        *,
        bool_symbols: Optional[Mapping[str, str]] = None,
        udint_symbols: Optional[Mapping[str, str]] = None,
        string_symbols: Optional[Mapping[str, str]] = None,
    ) -> None:
        self.config = config or AdsConnectionConfig()
        self.bool_symbols = dict(DEFAULT_BOOL_SYMBOLS)
        if bool_symbols:
            self.bool_symbols.update(bool_symbols)
        self.udint_symbols = dict(DEFAULT_UDINT_SYMBOLS)
        if udint_symbols:
            self.udint_symbols.update(udint_symbols)
        self.string_symbols = dict(DEFAULT_STRING_SYMBOLS)
        if string_symbols:
            self.string_symbols.update(string_symbols)

    @contextmanager
    def open_connection(self) -> Iterator[pyads.Connection]:
        plc = pyads.Connection(self.config.ams_net_id, self.config.port)
        plc.open()
        try:
            yield plc
        finally:
            plc.close()

    def resolve_bool_symbol(self, symbol_or_key: str) -> str:
        return self.bool_symbols.get(symbol_or_key, symbol_or_key)

    def resolve_udint_symbol(self, symbol_or_key: str) -> str:
        return self.udint_symbols.get(symbol_or_key, symbol_or_key)

    def resolve_string_symbol(self, symbol_or_key: str) -> str:
        return self.string_symbols.get(symbol_or_key, symbol_or_key)

    def read_bool(self, symbol_or_key: str) -> AdsReadResult:
        symbol = self.resolve_bool_symbol(symbol_or_key)
        with self.open_connection() as plc:
            value = bool(plc.read_by_name(symbol, pyads.PLCTYPE_BOOL))
        return AdsReadResult(symbol=symbol, value=value)

    def read_bool_snapshot(
        self,
        symbols_or_keys: Sequence[str],
    ) -> Dict[str, AdsReadResult]:
        resolved = [
            (symbol_or_key, self.resolve_bool_symbol(symbol_or_key))
            for symbol_or_key in symbols_or_keys
        ]
        with self.open_connection() as plc:
            return {
                symbol_or_key: AdsReadResult(
                    symbol=symbol,
                    value=bool(plc.read_by_name(symbol, pyads.PLCTYPE_BOOL)),
                )
                for symbol_or_key, symbol in resolved
            }

    def read_udint_snapshot(
        self,
        symbols_or_keys: Sequence[str],
    ) -> Dict[str, AdsReadResult]:
        resolved = [
            (symbol_or_key, self.resolve_udint_symbol(symbol_or_key))
            for symbol_or_key in symbols_or_keys
        ]
        with self.open_connection() as plc:
            return {
                symbol_or_key: AdsReadResult(
                    symbol=symbol,
                    value=int(plc.read_by_name(symbol, pyads.PLCTYPE_UDINT)),
                )
                for symbol_or_key, symbol in resolved
            }

    def read_udint(self, symbol_or_key: str) -> AdsReadResult:
        symbol = self.resolve_udint_symbol(symbol_or_key)
        with self.open_connection() as plc:
            value = int(plc.read_by_name(symbol, pyads.PLCTYPE_UDINT))
        return AdsReadResult(symbol=symbol, value=value)

    def read_string(self, symbol_or_key: str) -> AdsReadResult:
        symbol = self.resolve_string_symbol(symbol_or_key)
        with self.open_connection() as plc:
            value = str(plc.read_by_name(symbol, pyads.PLCTYPE_STRING))
        return AdsReadResult(symbol=symbol, value=value.rstrip("\x00"))

    def write_bool(self, symbol_or_key: str, value: bool) -> AdsWriteReceipt:
        symbol = self.resolve_bool_symbol(symbol_or_key)
        with self.open_connection() as plc:
            plc.write_by_name(symbol, bool(value), pyads.PLCTYPE_BOOL)
        return AdsWriteReceipt(symbol=symbol, value=bool(value))

    def write_udint(self, symbol_or_key: str, value: int) -> AdsWriteReceipt:
        symbol = self.resolve_udint_symbol(symbol_or_key)
        with self.open_connection() as plc:
            plc.write_by_name(symbol, int(value), pyads.PLCTYPE_UDINT)
        return AdsWriteReceipt(symbol=symbol, value=int(value))

    def write_string(self, symbol_or_key: str, value: str) -> AdsWriteReceipt:
        symbol = self.resolve_string_symbol(symbol_or_key)
        with self.open_connection() as plc:
            plc.write_by_name(symbol, str(value), pyads.PLCTYPE_STRING)
        return AdsWriteReceipt(symbol=symbol, value=str(value))

    def write_bool_values(self, values: Mapping[str, bool]) -> Dict[str, bool]:
        with self.open_connection() as plc:
            for key, value in values.items():
                plc.write_by_name(
                    self.resolve_bool_symbol(key),
                    bool(value),
                    pyads.PLCTYPE_BOOL,
                )
        return {key: bool(value) for key, value in values.items()}

    def pulse_bool_values(
        self,
        symbols_or_keys: Sequence[str],
        *,
        pulse_seconds: float = 0.1,
    ) -> Tuple[AdsWriteReceipt, ...]:
        if pulse_seconds < 0:
            raise ValueError("pulse_seconds muss >= 0 sein.")

        resolved_symbols = [
            self.resolve_bool_symbol(symbol_or_key) for symbol_or_key in symbols_or_keys
        ]

        with self.open_connection() as plc:
            for symbol in resolved_symbols:
                plc.write_by_name(symbol, True, pyads.PLCTYPE_BOOL)
            if pulse_seconds > 0:
                time.sleep(pulse_seconds)
            for symbol in resolved_symbols:
                plc.write_by_name(symbol, False, pyads.PLCTYPE_BOOL)

        receipts: List[AdsWriteReceipt] = []
        for symbol in resolved_symbols:
            receipts.append(AdsWriteReceipt(symbol=symbol, value=True))
            receipts.append(
                AdsWriteReceipt(
                    symbol=symbol,
                    value=False,
                    delay_seconds=float(pulse_seconds),
                    scheduled=False,
                )
            )
        return tuple(receipts)

    def read_skill_tracking(self) -> Dict[str, AdsReadResult]:
        return {
            "last_executed_skill": self.read_string("last_executed_skill"),
            "last_finished_skill": self.read_string("last_finished_skill"),
            "last_executed_process": self.read_string("last_executed_process"),
        }

    def _schedule_write(
        self,
        *,
        symbol: str,
        value: Any,
        plc_type: Any,
        delay_seconds: float,
    ) -> AdsWriteReceipt:
        def worker() -> None:
            try:
                time.sleep(delay_seconds)
                with self.open_connection() as plc:
                    plc.write_by_name(symbol, value, plc_type)
            except Exception as exc:
                print(
                    {
                        "scheduled_ads_write_failed": True,
                        "symbol": symbol,
                        "error": repr(exc),
                    }
                )

        thread = threading.Thread(target=worker, daemon=True)
        thread.start()
        return AdsWriteReceipt(
            symbol=symbol,
            value=value,
            delay_seconds=float(delay_seconds),
            scheduled=True,
        )

    def schedule_bool_write(
        self,
        symbol_or_key: str,
        value: bool,
        delay_seconds: float,
    ) -> AdsWriteReceipt:
        if delay_seconds <= 0:
            return self.write_bool(symbol_or_key, value)
        return self._schedule_write(
            symbol=self.resolve_bool_symbol(symbol_or_key),
            value=bool(value),
            plc_type=pyads.PLCTYPE_BOOL,
            delay_seconds=float(delay_seconds),
        )

    def schedule_udint_write(
        self,
        symbol_or_key: str,
        value: int,
        delay_seconds: float,
    ) -> AdsWriteReceipt:
        if delay_seconds <= 0:
            return self.write_udint(symbol_or_key, value)
        return self._schedule_write(
            symbol=self.resolve_udint_symbol(symbol_or_key),
            value=int(value),
            plc_type=pyads.PLCTYPE_UDINT,
            delay_seconds=float(delay_seconds),
        )

    def schedule_bool_sequence(
        self,
        events: Sequence[Tuple[float, str, bool]],
    ) -> List[AdsWriteReceipt]:
        return [
            self.schedule_bool_write(symbol_or_key, value, delay_seconds)
            for delay_seconds, symbol_or_key, value in events
        ]

    def schedule_udint_sequence(
        self,
        events: Sequence[Tuple[float, str, int]],
    ) -> List[AdsWriteReceipt]:
        return [
            self.schedule_udint_write(symbol_or_key, value, delay_seconds)
            for delay_seconds, symbol_or_key, value in events
        ]

    def start_bool_events(
        self,
        events: Sequence[BoolWriteEvent],
    ) -> List[AdsWriteReceipt]:
        return [
            self.schedule_bool_write(event.symbol_or_key, event.value, event.delay_seconds)
            for event in events
        ]

    def start_udint_events(
        self,
        events: Sequence[UdintWriteEvent],
    ) -> List[AdsWriteReceipt]:
        return [
            self.schedule_udint_write(event.symbol_or_key, event.value, event.delay_seconds)
            for event in events
        ]

    def start_sps_plan(
        self,
        plan: SpsStartPlan,
    ) -> Tuple[AdsWriteReceipt, ...]:
        receipts: List[AdsWriteReceipt] = []
        receipts.extend(self.start_bool_events(plan.bool_events))
        receipts.extend(self.start_udint_events(plan.udint_events))
        return tuple(receipts)

    def start_bool_change_logger(
        self,
        symbols_or_keys: Sequence[str],
        *,
        poll_interval_seconds: float = 0.05,
        include_initial_values: bool = True,
        print_prefix: str = "HW",
    ) -> Tuple[threading.Event, threading.Thread]:
        watch_list = tuple(symbols_or_keys)
        stop_event = threading.Event()
        start_time = time.monotonic()

        def worker() -> None:
            last_values: Dict[str, bool] = {}
            while not stop_event.is_set():
                try:
                    snapshot = self.read_bool_snapshot(watch_list)
                    elapsed_seconds = round(time.monotonic() - start_time, 3)
                    for symbol_or_key in watch_list:
                        result = snapshot[symbol_or_key]
                        current_value = bool(result.value)
                        previous_value = last_values.get(symbol_or_key)
                        if previous_value is None:
                            if include_initial_values:
                                print(
                                    {
                                        "event": f"{print_prefix}_initial",
                                        "symbol_or_key": symbol_or_key,
                                        "symbol": result.symbol,
                                        "value": current_value,
                                        "elapsed_seconds": elapsed_seconds,
                                    }
                                )
                        elif previous_value != current_value:
                            print(
                                {
                                    "event": f"{print_prefix}_change",
                                    "symbol_or_key": symbol_or_key,
                                    "symbol": result.symbol,
                                    "old_value": previous_value,
                                    "new_value": current_value,
                                    "elapsed_seconds": elapsed_seconds,
                                }
                            )
                        last_values[symbol_or_key] = current_value
                except Exception as exc:
                    print(
                        {
                            "event": f"{print_prefix}_logger_error",
                            "error": repr(exc),
                        }
                    )
                stop_event.wait(poll_interval_seconds)

        thread = threading.Thread(target=worker, daemon=True)
        thread.start()
        return stop_event, thread

    def read_encoder_snapshot(self) -> Dict[str, int]:
        return {
            name: int(self.read_udint(symbol).value)
            for name, symbol in self.udint_symbols.items()
            if name in {"horizontal_1", "horizontal_2", "vertical_1", "vertical_2"}
        }

    def read_hrl_signal_diagnostic(self) -> Dict[str, AdsReadResult]:
        return {
            "ls_inner_sim": self.read_bool("ls_inner"),
            "ls_inner_runtime": self.read_bool("GVL_HRL.HRL_LS_innen"),
            "ls_outer_sim": self.read_bool("ls_outer"),
            "ls_outer_runtime": self.read_bool("GVL_HRL.HRL_LS_aussen"),
        }

    def prepare_plc_for_skill_tests(
        self,
        *,
        reset_pulse_seconds: float = 0.1,
    ) -> Dict[str, bool]:
        values = {
            "sim": True,
            "notaus_a": True,
            "notaus_b": True,
            "hrl_reset_button": False,
            "hrl_start_button": True,
            "hrl_confirmation_button": False,
            "vsg_reset_button": False,
            "vsg_start_button": True,
            "vsg_confirmation_button": False,
            "ts_horizontal": False,
            "ts_vertical": False,
            "ts_ausleger_vorne": False,
            "ts_ausleger_hinten": True,
            "ls_inner": False,
            "ls_outer": False,
        }
        prepared = self.write_bool_values(values)
        self.pulse_bool_values(
            ("hrl_reset_button", "vsg_reset_button"),
            pulse_seconds=reset_pulse_seconds,
        )
        return prepared

    def prepare_vsg_for_compressor_test(
        self,
        *,
        workpiece_at_pickup: bool = True,
        reset_pulse_seconds: float = 0.1,
    ) -> Dict[str, bool]:
        values = {
            "sim": True,
            "notaus_a": True,
            "notaus_b": True,
            "vsg_reset_button": False,
            "vsg_start_button": True,
            "vsg_confirmation_button": False,
            "ls_outer": bool(workpiece_at_pickup),
        }
        prepared = self.write_bool_values(values)
        self.pulse_bool_values(
            ("vsg_reset_button",),
            pulse_seconds=reset_pulse_seconds,
        )
        return prepared

    def schedule_hrl_auslagern_ausleger_sequence(
        self,
        config: Optional[HrlAuslegerSequenceConfig] = None,
    ) -> List[AdsWriteReceipt]:
        return self.start_bool_events(self.build_hrl_auslagern_ausleger_events(config))

    def build_hrl_auslagern_ausleger_events(
        self,
        config: Optional[HrlAuslegerSequenceConfig] = None,
    ) -> Tuple[BoolWriteEvent, ...]:
        config = config or HrlAuslegerSequenceConfig()
        t0 = config.step30_start_seconds
        return (
            BoolWriteEvent(t0, "ts_ausleger_hinten", False),
            BoolWriteEvent(t0 + 0.8, "ts_ausleger_vorne", True),
            BoolWriteEvent(t0 + 1.1, "ts_ausleger_vorne", False),
            BoolWriteEvent(t0 + 1.9, "ts_ausleger_hinten", True),
        )

    def schedule_hrl_auslagern_conveyor_sequence(
        self,
        config: Optional[HrlConveyorSequenceConfig] = None,
    ) -> List[AdsWriteReceipt]:
        return self.start_bool_events(self.build_hrl_auslagern_conveyor_events(config))

    def build_hrl_auslagern_conveyor_events(
        self,
        config: Optional[HrlConveyorSequenceConfig] = None,
    ) -> Tuple[BoolWriteEvent, ...]:
        config = config or HrlConveyorSequenceConfig()
        config.validate()
        return (
            BoolWriteEvent(config.ls_inner_detect_seconds, "ls_inner", True),
            BoolWriteEvent(config.ls_inner_release_seconds, "ls_inner", False),
            BoolWriteEvent(config.ls_outer_detect_seconds, "ls_outer", True),
        )

    def schedule_hrl_auslagern_encoder_sequence(
        self,
        request: Optional[HrlAuslagernRequest] = None,
    ) -> List[AdsWriteReceipt]:
        return self.start_udint_events(self.build_hrl_auslagern_encoder_events(request))

    def build_hrl_auslagern_encoder_events(
        self,
        request: Optional[HrlAuslagernRequest] = None,
    ) -> Tuple[UdintWriteEvent, ...]:
        request = request or HrlAuslagernRequest()
        return (
            UdintWriteEvent(0.0, "horizontal_1", 0),
            UdintWriteEvent(0.0, "horizontal_2", 0),
            UdintWriteEvent(0.0, "vertical_1", 0),
            UdintWriteEvent(0.0, "vertical_2", 0),
            UdintWriteEvent(2.0, "horizontal_1", request.horizontal_shelf_i1),
            UdintWriteEvent(2.0, "horizontal_2", request.horizontal_shelf_i2),
            UdintWriteEvent(4.0, "vertical_1", request.vertical_shelf_i1),
            UdintWriteEvent(4.0, "vertical_2", request.vertical_shelf_i2),
            UdintWriteEvent(7.0, "horizontal_1", request.horizontal_transfer_i1),
            UdintWriteEvent(7.0, "horizontal_2", request.horizontal_transfer_i2),
            UdintWriteEvent(8.5, "vertical_1", request.vertical_transfer_i1),
            UdintWriteEvent(8.5, "vertical_2", request.vertical_transfer_i2),
        )

    def schedule_vsg_compressor_encoder_sequence(
        self,
        request: Optional[VsgCompressorControlRequest] = None,
        *,
        target_reached_seconds: float = 0.8,
    ) -> List[AdsWriteReceipt]:
        return self.start_udint_events(
            self.build_vsg_compressor_encoder_events(
                request,
                target_reached_seconds=target_reached_seconds,
            )
        )

    def build_vsg_compressor_encoder_events(
        self,
        request: Optional[VsgCompressorControlRequest] = None,
        *,
        target_reached_seconds: float = 0.8,
    ) -> Tuple[UdintWriteEvent, ...]:
        request = request or VsgCompressorControlRequest()
        return (
            UdintWriteEvent(0.0, "vsg_rotation_1", 0),
            UdintWriteEvent(0.0, "vsg_rotation_2", 0),
            UdintWriteEvent(0.0, "vsg_horizontal_1", 0),
            UdintWriteEvent(0.0, "vsg_horizontal_2", 0),
            UdintWriteEvent(0.0, "vsg_vertical_1", 0),
            UdintWriteEvent(0.0, "vsg_vertical_2", 0),
            UdintWriteEvent(
                target_reached_seconds,
                "vsg_rotation_1",
                request.encoder_target_position_01,
            ),
            UdintWriteEvent(
                target_reached_seconds,
                "vsg_rotation_2",
                request.encoder_target_position_02,
            ),
            UdintWriteEvent(
                target_reached_seconds,
                "vsg_horizontal_1",
                request.encoder_target_position_03,
            ),
            UdintWriteEvent(
                target_reached_seconds,
                "vsg_horizontal_2",
                request.encoder_target_position_04,
            ),
            UdintWriteEvent(
                target_reached_seconds,
                "vsg_vertical_1",
                request.encoder_target_position_05,
            ),
            UdintWriteEvent(
                target_reached_seconds,
                "vsg_vertical_2",
                request.encoder_target_position_06,
            ),
        )


class SkillOA_Simulator:
    def __init__(
        self,
        config: Optional[OpcUaConnectionConfig] = None,
        *,
        sps: Optional[SPS_Simulator] = None,
    ) -> None:
        self.config = config or OpcUaConnectionConfig()
        self.sps = sps

    def _build_client(self) -> Client:
        self.config.security.validate()

        client = Client(self.config.endpoint, timeout=self.config.request_timeout_seconds)
        client.application_uri = self.config.application_uri
        client.secure_channel_timeout = self.config.secure_channel_timeout_ms
        client.session_timeout = self.config.session_timeout_ms

        security_string = self.config.security.build_security_string()
        if security_string:
            client.set_security_string(security_string)

        if self.config.username is not None:
            client.set_user(self.config.username)
        if self.config.password is not None:
            client.set_password(self.config.password)
        return client

    @contextmanager
    def open_connection(self) -> Iterator[Client]:
        client = self._build_client()
        client.connect()
        try:
            yield client
        finally:
            client.disconnect()

    @staticmethod
    def _node_name(node: Any) -> str:
        browse_name = node.get_browse_name()
        return str(getattr(browse_name, "Name", browse_name))

    @staticmethod
    def _node_id_text(node: Any) -> str:
        return node.nodeid.to_string()

    @staticmethod
    def _node_class_name(node: Any) -> str:
        node_class = node.get_node_class()
        return str(getattr(node_class, "name", node_class))

    @staticmethod
    def _is_method_node(node: Any) -> bool:
        return int(node.get_node_class()) == 4

    def _find_child_by_name(self, root_node: Any, expected_name: str) -> Any:
        for child in root_node.get_children():
            if self._node_name(child) == expected_name:
                return child
        raise LookupError(
            f"Child '{expected_name}' nicht unter '{self._node_name(root_node)}' gefunden."
        )

    def _find_descendant_by_name(
        self,
        root_node: Any,
        expected_name: str,
        *,
        max_depth: int = 10,
    ) -> Any:
        queue: List[Tuple[Any, int]] = [(root_node, 0)]
        while queue:
            node, depth = queue.pop(0)
            if self._node_name(node) == expected_name:
                return node
            if depth >= max_depth:
                continue
            for child in node.get_children():
                queue.append((child, depth + 1))
        raise LookupError(f"Node '{expected_name}' wurde im OPC-UA-Baum nicht gefunden.")

    def _iter_descendants(
        self,
        root_node: Any,
        *,
        max_depth: int = 10,
    ) -> Iterator[Tuple[Any, int]]:
        queue: List[Tuple[Any, int]] = [(root_node, 0)]
        while queue:
            node, depth = queue.pop(0)
            yield node, depth
            if depth >= max_depth:
                continue
            for child in node.get_children():
                queue.append((child, depth + 1))

    def _get_skillset_node(self, client: Client) -> Any:
        if self.config.skillset_nodeid:
            return client.get_node(self.config.skillset_nodeid)

        objects_node = client.get_objects_node()
        search_root = objects_node
        if self.config.plc_root_name:
            search_root = self._find_descendant_by_name(
                objects_node,
                self.config.plc_root_name,
                max_depth=10,
            )
        return self._find_descendant_by_name(
            search_root,
            self.config.skillset_name,
            max_depth=10,
        )

    def list_server_endpoints(self) -> List[Dict[str, str]]:
        probe = Client(self.config.endpoint)
        endpoints = probe.connect_and_get_server_endpoints()
        return [
            {
                "EndpointUrl": endpoint.EndpointUrl,
                "SecurityMode": str(endpoint.SecurityMode),
                "SecurityPolicyUri": endpoint.SecurityPolicyUri,
            }
            for endpoint in endpoints
        ]

    def list_method_containers(self) -> Dict[str, Tuple[Dict[str, str], ...]]:
        with self.open_connection() as client:
            skillset_node = self._get_skillset_node(client)
            result: Dict[str, Tuple[Dict[str, str], ...]] = {}
            for child, _depth in self._iter_descendants(skillset_node, max_depth=10):
                if child == skillset_node:
                    continue
                method_children = [
                    grandchild
                    for grandchild in child.get_children()
                    if self._is_method_node(grandchild)
                ]
                if not method_children:
                    continue
                result[self._node_name(child)] = tuple(
                    {
                        "method_name": self._node_name(method_child),
                        "method_nodeid": self._node_id_text(method_child),
                        "node_class": self._node_class_name(method_child),
                    }
                    for method_child in method_children
                )
            return result

    def _get_method_container_nodes(self, client: Client) -> Dict[str, Any]:
        skillset_node = self._get_skillset_node(client)
        result: Dict[str, Any] = {}
        for child, _depth in self._iter_descendants(skillset_node, max_depth=10):
            if child == skillset_node:
                continue
            method_children = [
                grandchild for grandchild in child.get_children() if self._is_method_node(grandchild)
            ]
            if method_children:
                result[self._node_name(child)] = child
        return result

    def _get_container_method_nodes(self, container_node: Any) -> Dict[str, Any]:
        return {
            self._node_name(child): child
            for child in container_node.get_children()
            if self._is_method_node(child)
        }

    def _resolve_method_node(self, client: Client, reference: MethodReference) -> Any:
        reference.validate()
        if reference.method_nodeid:
            return client.get_node(reference.method_nodeid)

        container_nodes = self._get_method_container_nodes(client)
        if reference.container_name not in container_nodes:
            raise LookupError(
                f"Methoden-Container '{reference.container_name}' nicht gefunden."
            )

        method_nodes = self._get_container_method_nodes(container_nodes[reference.container_name])
        if reference.method_name not in method_nodes:
            raise LookupError(
                f"Methode '{reference.method_name}' nicht unter "
                f"'{reference.container_name}' gefunden."
            )
        return method_nodes[reference.method_name]

    def _get_argument_definitions(
        self,
        method_node: Any,
        *,
        property_name: str = "InputArguments",
    ) -> Tuple[MethodArgumentDefinition, ...]:
        try:
            property_node = method_node.get_child([f"0:{property_name}"])
        except Exception:
            return tuple()

        definitions: List[MethodArgumentDefinition] = []
        for argument in property_node.get_value():
            data_type = getattr(argument, "DataType", None)
            data_type_identifier = getattr(data_type, "Identifier", None)
            variant_type = None
            if data_type_identifier is not None:
                variant = BUILTIN_NODEID_TO_VARIANT.get(int(data_type_identifier))
                variant_type = str(variant) if variant is not None else None
            definitions.append(
                MethodArgumentDefinition(
                    name=getattr(argument, "Name", ""),
                    data_type_nodeid=data_type.to_string() if data_type is not None else None,
                    variant_type=variant_type,
                )
            )
        return tuple(definitions)

    def get_method_signature(self, reference: MethodReference) -> MethodSignature:
        with self.open_connection() as client:
            method_node = self._resolve_method_node(client, reference)
            parent_node = method_node.get_parent()
            return MethodSignature(
                method_name=self._node_name(method_node),
                method_nodeid=self._node_id_text(method_node),
                parent_name=self._node_name(parent_node),
                parent_nodeid=self._node_id_text(parent_node),
                inputs=self._get_argument_definitions(method_node, property_name="InputArguments"),
                outputs=self._get_argument_definitions(method_node, property_name="OutputArguments"),
            )

    def _build_typed_method_arguments(
        self,
        method_node: Any,
        values_by_name: Mapping[str, Any],
    ) -> List[ua.Variant]:
        input_arguments = self._get_argument_definitions(method_node, property_name="InputArguments")
        expected_names = [argument.name for argument in input_arguments]
        missing = [name for name in expected_names if name not in values_by_name]
        unexpected = sorted(set(values_by_name) - set(expected_names))
        if missing or unexpected:
            parts: List[str] = []
            if missing:
                parts.append(f"fehlend: {missing}")
            if unexpected:
                parts.append(f"unerwartet: {unexpected}")
            raise KeyError(
                "Methodenargumente passen nicht zur Signatur (" + ", ".join(parts) + ")."
            )

        variants: List[ua.Variant] = []
        for argument in input_arguments:
            value = values_by_name[argument.name]
            if argument.variant_type is None:
                variants.append(ua.Variant(value))
                continue

            variant_enum = next(
                (
                    variant
                    for variant in ua.VariantType
                    if str(variant) == argument.variant_type
                ),
                None,
            )
            variants.append(
                ua.Variant(value) if variant_enum is None else ua.Variant(value, variant_enum)
            )
        return variants

    def call_method(
        self,
        reference: MethodReference,
        values_by_name: Mapping[str, Any],
    ) -> MethodCallResult:
        with self.open_connection() as client:
            method_node = self._resolve_method_node(client, reference)
            parent_node = method_node.get_parent()
            input_arguments = self._get_argument_definitions(method_node, property_name="InputArguments")
            output_arguments = self._get_argument_definitions(
                method_node,
                property_name="OutputArguments",
            )
            typed_arguments = self._build_typed_method_arguments(method_node, values_by_name)

            request = ua.CallMethodRequest()
            request.ObjectId = parent_node.nodeid
            request.MethodId = method_node.nodeid
            request.InputArguments = typed_arguments

            call_result = parent_node.server.call([request])[0]
            status_value = int(call_result.StatusCode.value)
            status_name, status_doc = ua.status_codes.get_name_and_doc(status_value)

            if status_value & 0x80000000:
                call_result.StatusCode.check()

            raw_outputs = tuple(
                variant.Value for variant in getattr(call_result, "OutputArguments", [])
            )
            return MethodCallResult(
                method_name=self._node_name(method_node),
                method_nodeid=self._node_id_text(method_node),
                parent_name=self._node_name(parent_node),
                parent_nodeid=self._node_id_text(parent_node),
                status_code=status_value,
                status_code_hex=f"0x{status_value:08X}",
                status_name=status_name,
                status_doc=status_doc,
                status_is_good=call_result.StatusCode.is_good(),
                status_is_uncertain=(status_value & 0xC0000000) == 0x40000000,
                inputs={argument.name: values_by_name[argument.name] for argument in input_arguments},
                outputs={
                    argument.name: raw_outputs[index] if index < len(raw_outputs) else None
                    for index, argument in enumerate(output_arguments)
                },
                raw_outputs=raw_outputs,
            )

    @staticmethod
    def _payload_from_request(
        request: Mapping[str, Any] | HrlAuslagernRequest | VsgCompressorControlRequest,
    ) -> Dict[str, Any]:
        if isinstance(request, Mapping):
            return dict(request)
        return request.to_payload()

    def call_hrl_auslagern(
        self,
        request: Mapping[str, Any] | HrlAuslagernRequest,
    ) -> MethodCallResult:
        return self.call_method(
            MethodReference(method_nodeid=DEFAULT_HRL_AUSLAGERN_METHOD_NODEID),
            self._payload_from_request(request),
        )

    def get_hrl_auslagern_signature(self) -> MethodSignature:
        return self.get_method_signature(
            MethodReference(method_nodeid=DEFAULT_HRL_AUSLAGERN_METHOD_NODEID)
        )

    def call_vsg_compressor_control(
        self,
        request: Mapping[str, Any] | VsgCompressorControlRequest,
    ) -> MethodCallResult:
        return self.call_method(
            MethodReference(method_nodeid=DEFAULT_VSG_COMPRESSOR_METHOD_NODEID),
            self._payload_from_request(request),
        )

    def get_vsg_compressor_control_signature(self) -> MethodSignature:
        return self.get_method_signature(
            MethodReference(method_nodeid=DEFAULT_VSG_COMPRESSOR_METHOD_NODEID)
        )

    @staticmethod
    def _skill_name_from_call_result(call_result: MethodCallResult) -> str:
        return call_result.parent_name

    def write_last_finished_skill(self, skill_name: str) -> AdsWriteReceipt:
        if self.sps is None:
            raise RuntimeError(
                "write_last_finished_skill() braucht einen gebundenen SPS_Simulator."
            )
        return self.sps.write_string("last_finished_skill", skill_name)

    def document_last_finished_skill(
        self,
        result: SkillExecutionResult | MethodCallResult,
        *,
        skill_name: Optional[str] = None,
    ) -> Optional[AdsWriteReceipt]:
        call_result = result.call if isinstance(result, SkillExecutionResult) else result
        if not call_result.is_successful():
            return None
        resolved_skill_name = skill_name or self._skill_name_from_call_result(call_result)
        return self.write_last_finished_skill(resolved_skill_name)

    def reset_last_finished_skill(self) -> AdsWriteReceipt:
        return self.write_last_finished_skill("")

    def build_hrl_auslagern_start_plan(
        self,
        request: Mapping[str, Any] | HrlAuslagernRequest,
        *,
        schedule_encoder_sequence: bool = True,
        ausleger_sequence: Optional[HrlAuslegerSequenceConfig] = HrlAuslegerSequenceConfig(),
        conveyor_sequence: Optional[HrlConveyorSequenceConfig] = HrlConveyorSequenceConfig(),
    ) -> SkillStartPlan:
        hrl_request = (
            request
            if isinstance(request, HrlAuslagernRequest)
            else HrlAuslagernRequest(
                method_call=bool(request["MethodCall"]),
                horizontal_shelf_i1=int(request["HorizontalShelf_I1"]),
                horizontal_shelf_i2=int(request["HorizontalShelf_I2"]),
                vertical_shelf_i1=int(request["VerticalShelf_I1"]),
                vertical_shelf_i2=int(request["VerticalShelf_I2"]),
                horizontal_transfer_i1=int(request["HorizontalTransfer_I1"]),
                horizontal_transfer_i2=int(request["HorizontalTransfer_I2"]),
                vertical_transfer_i1=int(request["VerticalTransfer_I1"]),
                vertical_transfer_i2=int(request["VerticalTransfer_I2"]),
                timeout_ms=int(request["Timeout"]),
            )
        )

        bool_events: List[BoolWriteEvent] = []
        udint_events: List[UdintWriteEvent] = []
        if schedule_encoder_sequence or ausleger_sequence is not None or conveyor_sequence is not None:
            if self.sps is None:
                raise RuntimeError(
                    "Fuer SPS-Ereignisse wird ein gebundener SPS_Simulator benoetigt."
                )
        if schedule_encoder_sequence:
            udint_events.extend(self.sps.build_hrl_auslagern_encoder_events(hrl_request))
        if ausleger_sequence is not None:
            bool_events.extend(self.sps.build_hrl_auslagern_ausleger_events(ausleger_sequence))
        if conveyor_sequence is not None:
            bool_events.extend(self.sps.build_hrl_auslagern_conveyor_events(conveyor_sequence))

        return SkillStartPlan(
            name="HRL_Auslagern",
            method=MethodReference(method_nodeid=DEFAULT_HRL_AUSLAGERN_METHOD_NODEID),
            payload=hrl_request.to_payload(),
            sps_plan=SpsStartPlan(
                bool_events=tuple(bool_events),
                udint_events=tuple(udint_events),
            ),
        )

    def build_vsg_compressor_control_start_plan(
        self,
        request: Mapping[str, Any] | VsgCompressorControlRequest,
        *,
        schedule_encoder_sequence: bool = True,
        target_reached_seconds: float = 0.8,
    ) -> SkillStartPlan:
        vsg_request = (
            request
            if isinstance(request, VsgCompressorControlRequest)
            else VsgCompressorControlRequest(
                method_call=bool(request["MethodCall"]),
                destination_reached=bool(request["DestinationReached"]),
                encoder_target_position_01=int(request["EncoderTargetPosition_01"]),
                encoder_target_position_02=int(request["EncoderTargetPosition_02"]),
                encoder_target_position_03=int(request["EncoderTargetPosition_03"]),
                encoder_target_position_04=int(request["EncoderTargetPosition_04"]),
                encoder_target_position_05=int(request["EncoderTargetPosition_05"]),
                encoder_target_position_06=int(request["EncoderTargetPosition_06"]),
            )
        )

        udint_events: List[UdintWriteEvent] = []
        if schedule_encoder_sequence:
            if self.sps is None:
                raise RuntimeError(
                    "Fuer SPS-Ereignisse wird ein gebundener SPS_Simulator benoetigt."
                )
            udint_events.extend(
                self.sps.build_vsg_compressor_encoder_events(
                    vsg_request,
                    target_reached_seconds=target_reached_seconds,
                )
            )

        return SkillStartPlan(
            name="VSG_CompressorControl",
            method=MethodReference(method_nodeid=DEFAULT_VSG_COMPRESSOR_METHOD_NODEID),
            payload=vsg_request.to_payload(),
            sps_plan=SpsStartPlan(udint_events=tuple(udint_events)),
        )

    def start_skill_plan(
        self,
        plan: SkillStartPlan,
    ) -> SkillExecutionResult:
        scheduled_writes: Tuple[AdsWriteReceipt, ...] = tuple()
        if not plan.sps_plan.is_empty():
            if self.sps is None:
                raise RuntimeError(
                    "Der SkillStartPlan enthaelt SPS-Ereignisse, aber kein SPS_Simulator ist gebunden."
                )
            scheduled_writes = self.sps.start_sps_plan(plan.sps_plan)

        call_result = self.call_method(plan.method, plan.payload)
        return SkillExecutionResult(
            prepared_signals={},
            scheduled_writes=scheduled_writes,
            call=call_result,
        )

    def run_hrl_auslagern(
        self,
        request: Mapping[str, Any] | HrlAuslagernRequest,
        *,
        prepare_plc: bool = True,
        schedule_encoder_sequence: bool = True,
        ausleger_sequence: Optional[HrlAuslegerSequenceConfig] = HrlAuslegerSequenceConfig(),
        conveyor_sequence: Optional[HrlConveyorSequenceConfig] = HrlConveyorSequenceConfig(),
    ) -> SkillExecutionResult:
        if self.sps is None:
            raise RuntimeError("run_hrl_auslagern() braucht einen gebundenen SPS_Simulator.")

        prepared_signals = (
            self.sps.prepare_plc_for_skill_tests() if prepare_plc else {}
        )
        plan = self.build_hrl_auslagern_start_plan(
            request,
            schedule_encoder_sequence=schedule_encoder_sequence,
            ausleger_sequence=ausleger_sequence,
            conveyor_sequence=conveyor_sequence,
        )
        started = self.start_skill_plan(plan)
        return SkillExecutionResult(
            prepared_signals=prepared_signals,
            scheduled_writes=started.scheduled_writes,
            call=started.call,
        )

    def run_vsg_compressor_control(
        self,
        request: Mapping[str, Any] | VsgCompressorControlRequest,
        *,
        prepare_plc: bool = True,
        workpiece_at_pickup: bool = True,
        schedule_encoder_sequence: bool = True,
        target_reached_seconds: float = 0.8,
    ) -> SkillExecutionResult:
        if self.sps is None:
            raise RuntimeError(
                "run_vsg_compressor_control() braucht einen gebundenen SPS_Simulator."
            )

        vsg_request = (
            request
            if isinstance(request, VsgCompressorControlRequest)
            else VsgCompressorControlRequest(
                method_call=bool(request["MethodCall"]),
                destination_reached=bool(request["DestinationReached"]),
                encoder_target_position_01=int(request["EncoderTargetPosition_01"]),
                encoder_target_position_02=int(request["EncoderTargetPosition_02"]),
                encoder_target_position_03=int(request["EncoderTargetPosition_03"]),
                encoder_target_position_04=int(request["EncoderTargetPosition_04"]),
                encoder_target_position_05=int(request["EncoderTargetPosition_05"]),
                encoder_target_position_06=int(request["EncoderTargetPosition_06"]),
            )
        )

        prepared_signals = (
            self.sps.prepare_vsg_for_compressor_test(
                workpiece_at_pickup=workpiece_at_pickup
            )
            if prepare_plc
            else {}
        )
        plan = self.build_vsg_compressor_control_start_plan(
            vsg_request,
            schedule_encoder_sequence=schedule_encoder_sequence,
            target_reached_seconds=target_reached_seconds,
        )
        started = self.start_skill_plan(plan)
        return SkillExecutionResult(
            prepared_signals=prepared_signals,
            scheduled_writes=started.scheduled_writes,
            call=started.call,
        )


__all__ = [
    "AdsConnectionConfig",
    "AdsReadResult",
    "AdsWriteReceipt",
    "DEFAULT_BOOL_SYMBOLS",
    "DEFAULT_HRL_AUSLAGERN_METHOD_NODEID",
    "DEFAULT_HRL_SKILLSET_NODEID",
    "DEFAULT_STRING_SYMBOLS",
    "DEFAULT_UDINT_SYMBOLS",
    "DEFAULT_VSG_COMPRESSOR_METHOD_NODEID",
    "HrlAuslagernRequest",
    "HrlAuslegerSequenceConfig",
    "HrlConveyorSequenceConfig",
    "MethodArgumentDefinition",
    "MethodCallResult",
    "MethodReference",
    "MethodSignature",
    "OpcUaConnectionConfig",
    "OpcUaSecurityConfig",
    "SPS_Simulator",
    "SkillExecutionResult",
    "SkillOA_Simulator",
    "VsgCompressorControlRequest",
]
