from dataclasses import dataclass, field

from pelumas_agent.db.models import Product

CHECK_ORDER = [
    "connection_size_in",
    "max_pressure_bar",
    "flow_range",
    "fluid",
    "flange_rating",
    "accuracy_pct",
]

PRESSURE_MARGIN = 0.10


@dataclass
class FitmentRequirement:
    connection_size_in: float | None = None
    system_pressure_bar: float | None = None
    flow_lpm: float | None = None
    fluid: str | None = None
    flange_rating: str | None = None
    accuracy_pct: float | None = None

    def has_any(self) -> bool:
        return any(
            value is not None
            for value in (
                self.connection_size_in,
                self.system_pressure_bar,
                self.flow_lpm,
                self.fluid,
                self.flange_rating,
                self.accuracy_pct,
            )
        )


@dataclass
class FitmentResult:
    verdict: str
    dimension: str | None = None
    detail: str = ""
    checked: list[str] = field(default_factory=list)


def _spec_value(product: Product, key: str) -> float | None:
    for spec in product.specs:
        if spec.key == key and spec.value_num is not None:
            return spec.value_num
    return None


def _spec_text(product: Product, key: str) -> str | None:
    for spec in product.specs:
        if spec.key == key and spec.value_text:
            return spec.value_text.lower()
    return None


def evaluate_fitment(product: Product, req: FitmentRequirement) -> FitmentResult:
    checked: list[str] = []

    if req.connection_size_in is not None:
        size = _spec_value(product, "connection_size_in")
        checked.append("connection_size_in")
        if size is None:
            return FitmentResult(
                "needs_confirmation",
                "connection_size_in",
                "ukuran sambungan tidak dipublikasikan",
                checked,
            )
        if abs(size - req.connection_size_in) > 1e-9:
            return FitmentResult(
                "does_not_fit",
                "connection_size_in",
                f"ukuran pembeli {_fmt(req.connection_size_in)} inch, "
                f"meter {_fmt(size)} inch",
                checked,
            )

    if req.system_pressure_bar is not None:
        max_pressure = _spec_value(product, "max_pressure_bar")
        checked.append("max_pressure_bar")
        if max_pressure is None:
            return FitmentResult(
                "needs_confirmation",
                "max_pressure_bar",
                "tekanan kerja maksimum tidak dipublikasikan",
                checked,
            )
        if max_pressure < req.system_pressure_bar * (1 + PRESSURE_MARGIN):
            return FitmentResult(
                "does_not_fit",
                "max_pressure_bar",
                f"tekanan sistem {req.system_pressure_bar} bar butuh margin 10%, "
                f"meter hanya {max_pressure} bar",
                checked,
            )

    if req.flow_lpm is not None:
        flow_min = _spec_value(product, "flow_min_lpm")
        flow_max = _spec_value(product, "flow_max_lpm")
        checked.append("flow_range")
        if flow_min is None or flow_max is None:
            return FitmentResult(
                "needs_confirmation",
                "flow_range",
                "rentang aliran tidak dipublikasikan",
                checked,
            )
        if req.flow_lpm > flow_max:
            return FitmentResult(
                "does_not_fit",
                "flow_range",
                f"aliran {req.flow_lpm} lpm di atas maksimum meter {flow_max} lpm",
                checked,
            )
        if req.flow_lpm < flow_min:
            return FitmentResult(
                "needs_confirmation",
                "flow_range",
                f"aliran {req.flow_lpm} lpm di bawah minimum meter {flow_min} lpm, "
                "akurasi menurun",
                checked,
            )

    if req.fluid is not None:
        fluids = _spec_text(product, "fluid")
        checked.append("fluid")
        if fluids is None:
            return FitmentResult(
                "needs_confirmation",
                "fluid",
                "dukungan fluida tidak dipublikasikan",
                checked,
            )
        wanted = req.fluid.lower().replace(" ", "_")
        supported = fluids.replace(" ", "_")
        if wanted not in supported:
            return FitmentResult(
                "does_not_fit",
                "fluid",
                f"fluida {req.fluid} tidak ada dalam daftar dukungan meter",
                checked,
            )

    if req.flange_rating is not None:
        rating = _spec_text(product, "flange_rating")
        checked.append("flange_rating")
        if rating is None:
            return FitmentResult(
                "needs_confirmation",
                "flange_rating",
                "rating flange tidak dipublikasikan",
                checked,
            )
        if req.flange_rating.lower() not in rating and rating not in req.flange_rating.lower():
            return FitmentResult(
                "needs_confirmation",
                "flange_rating",
                f"flange {req.flange_rating} perlu dicek kompatibilitas/adaptor",
                checked,
            )

    if req.accuracy_pct is not None:
        accuracy = _spec_value(product, "accuracy_pct")
        checked.append("accuracy_pct")
        if accuracy is None:
            return FitmentResult(
                "needs_confirmation",
                "accuracy_pct",
                "akurasi tidak dipublikasikan, tidak bisa klaim kepatuhan standar",
                checked,
            )
        if accuracy > req.accuracy_pct:
            return FitmentResult(
                "does_not_fit",
                "accuracy_pct",
                f"akurasi meter {accuracy}% di bawah kebutuhan {req.accuracy_pct}%",
                checked,
            )

    if not checked:
        return FitmentResult("needs_confirmation", None, "tidak ada dimensi untuk dicek")
    return FitmentResult("fit", None, "semua dimensi yang dicek lolos", checked)


def _fmt(value: float) -> str:
    if value == int(value):
        return str(int(value))
    return str(value)
