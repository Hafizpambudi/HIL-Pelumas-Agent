import json
import re

from pelumas_agent.llm.base import LLMClient, LLMMessage, LLMResponse, ToolCall
from pelumas_agent.orchestrator.extract import (
    detect_intent,
    extract_connection_size,
    extract_flow_lpm,
    extract_fluid,
    extract_pressure_bar,
)
from pelumas_agent.orchestrator.prompts import DISCLOSURE

_CHUNK_SPLIT = re.compile(r"\b(sama|dengan|dan|vs|versus|atau)\b", re.IGNORECASE)
_TOKEN_STRIP = re.compile(
    r"\b(bedanya|perbedaan|bandingkan|banding|compare|apa|itu|yang|untuk|buat|berapa)\b",
    re.IGNORECASE,
)


def _state_value(state_line: str, key: str) -> str | None:
    for chunk in state_line.split(";"):
        chunk = chunk.strip()
        if chunk.startswith(key + "="):
            return chunk[len(key) + 1 :]
    return None


class MockLLM(LLMClient):
    def complete(
        self,
        system: str,
        messages: list[LLMMessage],
        tools: list[dict] | None = None,
    ) -> LLMResponse:
        state_line = next((m.content for m in messages if m.role == "state"), "")
        user_messages = [m for m in messages if m.role == "user"]
        if not user_messages:
            return LLMResponse(text="Ada yang bisa saya bantu terkait produk kami?")
        last_user = user_messages[-1].content
        intents = detect_intent(last_user)

        tool_results = []
        for message in messages:
            if message.role == "tool":
                try:
                    tool_results.append(json.loads(message.content))
                except (ValueError, TypeError):
                    continue

        if intents["bot_question"]:
            return LLMResponse(text=DISCLOSURE)

        if intents["negotiation"]:
            return LLMResponse(
                tool_calls=[
                    ToolCall(
                        name="handoff",
                        arguments={
                            "reason": "negosiasi",
                            "summary": "Pembeli meminta diskon/negosiasi harga.",
                        },
                    )
                ]
            )

        if not tool_results:
            return self._first_action(last_user, intents, state_line)

        return self._react(last_user, intents, state_line, tool_results)

    def _first_action(self, text: str, intents: dict, state_line: str) -> LLMResponse:
        resolved_part = _state_value(state_line, "part")

        if intents["comparison"]:
            chunks = _CHUNK_SPLIT.split(text)
            refs = []
            for chunk in chunks:
                if not chunk or _CHUNK_SPLIT.fullmatch(chunk.strip() or ""):
                    continue
                cleaned = _TOKEN_STRIP.sub("", chunk).strip(" ,?!")
                if cleaned and not cleaned.lower().startswith(("bedanya", "banding")):
                    refs.append(cleaned)
            refs = [r for r in refs if re.search(r"[a-z0-9]", r.lower())][:4]
            if len(refs) >= 2:
                return LLMResponse(
                    tool_calls=[ToolCall(name="compare_specs", arguments={"part_nos": refs[:2]})]
                )

        if intents["substitution"]:
            ref = resolved_part or text
            return LLMResponse(
                tool_calls=[ToolCall(name="find_equivalent", arguments={"part_no": ref})]
            )

        if intents["availability"] and resolved_part:
            return LLMResponse(
                tool_calls=[
                    ToolCall(name="check_availability", arguments={"part_no": resolved_part})
                ]
            )

        arguments = {"query": text}
        fluid = extract_fluid(text)
        if fluid:
            arguments["fluid"] = fluid
        size = extract_connection_size(text)
        if size is not None:
            arguments["connection_size_in"] = size
        flow = extract_flow_lpm(text)
        if flow is not None:
            arguments["flow_lpm"] = flow
        pressure = extract_pressure_bar(text)
        if pressure is not None:
            arguments["min_pressure_bar"] = pressure
        return LLMResponse(tool_calls=[ToolCall(name="search_products", arguments=arguments)])

    def _react(
        self, text: str, intents: dict, state_line: str, tool_results: list[dict]
    ) -> LLMResponse:
        result = tool_results[-1]

        if "error" in result:
            return LLMResponse(
                text=(
                    "Maaf, datanya belum bisa saya ambil. "
                    "Bisa sebutkan part number atau foto nameplate-nya?"
                )
            )

        if result.get("found") is False:
            return LLMResponse(
                text=(
                    "Item tersebut tidak ketemu di katalog kami. "
                    "Boleh kirim part number persisnya atau foto nameplate?"
                )
            )

        if "tier" in result:
            return self._search_reply(text, intents, result)

        if "state" in result and "source" in result:
            return self._availability_reply(result, state_line)

        if "equivalents" in result:
            return self._equivalent_reply(result)

        if "differing_dimensions" in result:
            return self._compare_reply(result)

        if result.get("status") == "handed_off":
            return LLMResponse(text="Baik, saya teruskan ke admin kami ya. Mohon ditunggu.")

        if "products" in result:
            return self._search_reply(text, intents, {"tier": "exact", **result})

        return LLMResponse(text="Ada lagi yang bisa saya bantu?")

    def _search_reply(self, text: str, intents: dict, result: dict) -> LLMResponse:
        products = result.get("products", [])
        if not products:
            return LLMResponse(
                text=(
                    "Saya tidak menemukan item itu di katalog kami. "
                    "Boleh kirim part number persisnya atau foto nameplate-nya?"
                )
            )

        tier = result.get("tier", "exact")
        if tier == "semantic":
            lines = ["Yang paling mendekati dari katalog kami (kandidat, perlu konfirmasi):"]
            for product in products[:3]:
                lines.append(f"- {product['name']}")
            lines.append("Apakah salah satunya yang dimaksud?")
            return LLMResponse(text="\n".join(lines))

        if len(products) > 1:
            lines = ["Ada beberapa kandidat:"]
            for product in products[:3]:
                lines.append(f"- {product['name']}")
            lines.append("Yang mana yang dimaksud?")
            return LLMResponse(text="\n".join(lines))

        product = products[0]
        lines = [self._spec_summary(product)]
        if intents["price"]:
            lines.append(
                "Untuk harga dan ketersediaan, saya siapkan RFQ dan teruskan ke admin kami ya."
            )
        elif intents["availability"]:
            pass
        else:
            lines.append("Ada spesifikasi atau kebutuhan tertentu yang mau dicocokkan?")
        return LLMResponse(text="\n\n".join(lines))

    def _availability_reply(self, result: dict, state_line: str) -> LLMResponse:
        state = result.get("state")
        if state == "available":
            return LLMResponse(text="Berdasarkan data terakhir, unit ini tersedia.")
        if state == "indent":
            lead = result.get("lead_time_days")
            lead_text = f" estimasi {lead} hari," if lead else ""
            return LLMResponse(
                text=(
                    f"Item ini statusnya indent,{lead_text} tidak ready di gudang. "
                    "Mau lanjut menunggu indent, atau saya carikan alternatif?"
                )
            )
        if state == "discontinued":
            return LLMResponse(
                tool_calls=[
                    ToolCall(
                        name="find_equivalent",
                        arguments={"part_no": result.get("part_no", state_line)},
                    )
                ]
            )
        return LLMResponse(
            text=(
                "Ketersediaannya perlu saya cek dulu ke gudang. "
                "Nanti saya kabari secepatnya. Mau sambil saya siapkan RFQ-nya?"
            )
        )

    def _equivalent_reply(self, result: dict) -> LLMResponse:
        equivalents = result.get("equivalents", [])
        if not equivalents:
            return LLMResponse(
                text=(
                    "Saya belum punya kandidat pengganti yang terverifikasi untuk item ini. "
                    "Mau saya teruskan ke admin untuk dicarikan manual?"
                )
            )
        lines = ["Kandidat pengganti (perlu konfirmasi teknis):"]
        for equivalent in equivalents:
            line = f"- {equivalent['name']}"
            diffs = equivalent.get("differing_dims") or {}
            if diffs:
                diff_text = ", ".join(f"{k}: {v}" for k, v in diffs.items())
                line += f" (beda: {diff_text})"
            lines.append(line)
        lines.append("Mau saya lanjutkan dengan salah satunya, atau langsung ke admin?")
        return LLMResponse(text="\n".join(lines))

    def _compare_reply(self, result: dict) -> LLMResponse:
        rows = result.get("differing_dimensions", [])
        names = result.get("products", [])
        if not rows:
            return LLMResponse(text="Dari data katalog, dimensi yang dipublikasikan sama.")
        lines = [f"Perbandingan {' vs '.join(names)} — hanya dimensi yang berbeda:"]
        for row in rows:
            values = row["values"]
            detail = ", ".join(f"{name}: {value}" for name, value in values.items())
            lines.append(f"- {row['dimension']}: {detail}")
        return LLMResponse(text="\n".join(lines))

    def _spec_summary(self, product: dict) -> str:
        lines = [f"{product['name']} ({product.get('part_no') or 'tanpa part number'})"]
        label_map = {
            "connection_size_in": "Sambungan",
            "connection_type": "Tipe koneksi",
            "max_pressure_bar": "Tekanan maks",
            "flow_min_lpm": "Aliran min",
            "flow_max_lpm": "Aliran maks",
            "fluid": "Fluida",
            "flange_rating": "Flange",
            "accuracy_pct": "Akurasi",
        }
        for spec in product.get("specs", []):
            label = label_map.get(spec["key"])
            if not label:
                continue
            value = spec.get("value_text") or spec.get("value_num")
            if value is None:
                continue
            lines.append(f"- {label}: {value}")
        if product.get("data_confidence") == "low":
            lines.append("Data produk ini terbatas, sebagian perlu konfirmasi.")
        return "\n".join(lines)
