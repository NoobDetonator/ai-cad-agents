"""Turbina Savonius de mesa — vitrine do TALOS dirigida inteiramente via MCP.

Duas peças, zero parafusos: o rotor de três pás em S carrega um rolamento
print-in-place fundido no cubo e assenta no pino cônico da base. Todos os
sketches fecham em 0 graus de liberdade e as dimensões-chave são dirigidas
por parâmetros mestres. O script exige o FreeCAD aberto com o Workbench
TALOS MCP ativo e um documento "TurbinaSavonius".
"""
import asyncio
import json
import math
import sys
from pathlib import Path
from uuid import uuid4

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SERVER_EXE = PROJECT_ROOT / ".venv" / "Scripts" / "talos-freecad-mcp.exe"
OUT_DIR = Path(__file__).resolve().parent
REPORT: dict[str, object] = {"criteria": {}}

DISCO_R = 75.0
CUBO_R = 16.0
PA_CENTRO = 48.0
PA_R = 24.0
PA_PAREDE = 2.4
ROLAMENTO_VOL_KEY = "rolamento_volume_mm3"


def text_of(result):
    return "\n".join(b.text for b in result.content if getattr(b, "text", None))


class Driver:
    def __init__(self, session: ClientSession) -> None:
        self.session = session
        self.mutations = 0
        self.reads = 0

    async def modify(self, name: str, arguments: dict) -> dict:
        self.mutations += 1
        request_id = str(uuid4())
        for _ in range(60):
            res = await self.session.call_tool(
                "request_cad_tool",
                {"name": name, "arguments": arguments, "request_id": request_id},
            )
            body = json.loads(text_of(res))
            if body.get("status") not in ("pending_confirmation", "running"):
                break
            await asyncio.sleep(1.5)
        if body.get("status") != "completed":
            raise RuntimeError(f"{name} -> {json.dumps(body, ensure_ascii=False)}")
        return body["result"]

    async def read(self, name: str, arguments: dict) -> dict:
        self.reads += 1
        res = await self.session.call_tool(
            "execute_cad_read_tool", {"name": name, "arguments": arguments}
        )
        payload = json.loads(text_of(res))
        if isinstance(payload, dict) and payload.get("status") == "failed":
            raise RuntimeError(f"{name} -> {json.dumps(payload, ensure_ascii=False)}")
        return payload


def close(expected: float, actual: float, tolerance: float = 1e-4) -> bool:
    return math.isclose(expected, actual, rel_tol=tolerance)


def rotor_body_volume(altura_pas: float, espessura_pa: float,
                      espessura_disco: float) -> float:
    disco = math.pi * (DISCO_R**2 - CUBO_R**2) * espessura_disco
    halfpipe = math.pi / 2 * (PA_R**2 - (PA_R - espessura_pa) ** 2) * altura_pas
    return disco + 3 * halfpipe


def rotor_volume(altura_pas: float, espessura_pa: float,
                 espessura_disco: float, rolamento: float) -> float:
    overlap = math.pi * (17.0**2 - CUBO_R**2) * min(espessura_disco, 8.0)
    return (rotor_body_volume(altura_pas, espessura_pa, espessura_disco)
            + rolamento - overlap)


async def dim(d, sketch, ctype, geometry, value, name=None, expression=None,
              **kw):
    added = await d.modify(
        "cad.add_sketch_dimensional_constraint",
        {"sketch": sketch, "constraint_type": ctype, "geometry": geometry,
         "value": value, **kw},
    )
    if name is not None:
        await d.modify(
            "cad.rename_sketch_constraint",
            {"sketch": sketch, "constraint": added["added_constraint"],
             "name": name},
        )
    if expression is not None:
        await d.modify(
            "cad.bind_sketch_datum",
            {"sketch": sketch, "constraint": name, "expression": expression},
        )


async def geo(d, sketch, ctype, first, **kw):
    payload = {"sketch": sketch, "constraint_type": ctype,
               "first_geometry": first}
    payload.update(kw)
    await d.modify("cad.add_sketch_geometric_constraint", payload)


async def assert_zero_dof(d, sketch):
    status = await d.read("cad.get_sketch_status", {"sketch": sketch})
    assert status["fully_constrained"] is True, (sketch, status)


async def main() -> None:
    params = StdioServerParameters(command=str(SERVER_EXE), args=[])
    async with stdio_client(params) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            d = Driver(session)

            context = await d.read(
                "cad.get_context_snapshot",
                {"detail_level": "work", "max_objects": 5, "cursor": 0},
            )
            assert context["document_name"] == "TurbinaSavonius", context

            await d.modify("cad.create_parameter_set", {"name": "Params"})
            for pname, value in (
                ("diametro_disco", 150), ("espessura_disco", 6),
                ("altura_pas", 90), ("espessura_pa", PA_PAREDE),
                ("diametro_base", 160), ("espessura_base", 6),
                ("pino_diametro", 9.6), ("pino_altura", 28),
                ("pa_raio", PA_R), ("pa_centro", PA_CENTRO),
            ):
                await d.modify(
                    "cad.set_master_parameter",
                    {"name": pname, "value": value, "kind": "length"},
                )
            print("[1] oito parametros mestres")

            # --- Rotor: disco vazado ------------------------------------
            await d.modify("cad.create_body", {"name": "Rotor"})
            await d.modify(
                "cad.create_body_sketch",
                {"body": "Rotor", "plane": "xy", "name": "EsbocoDisco"},
            )
            await d.modify(
                "cad.add_sketch_circle",
                {"sketch": "EsbocoDisco", "center_x": 0, "center_y": 0,
                 "radius": DISCO_R},
            )
            await dim(d, "EsbocoDisco", "radius", 0, DISCO_R, "disco_raio",
                      "Params.diametro_disco / 2")
            await geo(d, "EsbocoDisco", "concentric", 0, second_geometry=-1)
            await assert_zero_dof(d, "EsbocoDisco")
            await d.modify(
                "cad.add_pad",
                {"sketch": "EsbocoDisco", "length": 6, "name": "PadDisco"},
            )
            await d.modify(
                "cad.bind_feature_parameter",
                {"feature": "PadDisco", "parameter": "length",
                 "expression": "Params.espessura_disco"},
            )
            await d.modify(
                "cad.create_body_sketch",
                {"body": "Rotor", "plane": "xy", "name": "EsbocoFuroCubo"},
            )
            await d.modify(
                "cad.add_sketch_circle",
                {"sketch": "EsbocoFuroCubo", "center_x": 0, "center_y": 0,
                 "radius": CUBO_R},
            )
            await dim(d, "EsbocoFuroCubo", "radius", 0, CUBO_R)
            await geo(d, "EsbocoFuroCubo", "concentric", 0, second_geometry=-1)
            await assert_zero_dof(d, "EsbocoFuroCubo")
            await d.modify(
                "cad.add_pocket",
                {"sketch": "EsbocoFuroCubo", "length": 1, "through_all": True,
                 "reversed": True, "name": "FuroCubo"},
            )
            print("[2] disco vazado 0 DoF")

            # --- Pa em meia-coroa, totalmente restrita ------------------
            await d.modify(
                "cad.create_face_sketch",
                {"body": "Rotor",
                 "face": {"kind": "largest_planar_face", "normal": "+z"},
                 "name": "EsbocoPa"},
            )
            inner_r = PA_R - PA_PAREDE
            await d.modify(
                "cad.add_sketch_arc",
                {"sketch": "EsbocoPa", "center_x": PA_CENTRO, "center_y": 0,
                 "radius": PA_R, "start_angle": 180, "end_angle": 360},
            )
            await d.modify(
                "cad.add_sketch_arc",
                {"sketch": "EsbocoPa", "center_x": PA_CENTRO, "center_y": 0,
                 "radius": inner_r, "start_angle": 180, "end_angle": 360},
            )
            await d.modify(
                "cad.add_sketch_line",
                {"sketch": "EsbocoPa", "x1": PA_CENTRO - PA_R, "y1": 0,
                 "x2": PA_CENTRO - inner_r, "y2": 0},
            )
            await d.modify(
                "cad.add_sketch_line",
                {"sketch": "EsbocoPa", "x1": PA_CENTRO + inner_r, "y1": 0,
                 "x2": PA_CENTRO + PA_R, "y2": 0},
            )
            # Geometricas primeiro, cotas depois, binds somente com 0 DoF:
            # vincular expressao em sketch subrestrito deixa o solver livre
            # para invalidar o perfil durante o re-solve.
            await geo(d, "EsbocoPa", "coincident", 0, second_geometry=2,
                      first_position="start", second_position="start")
            await geo(d, "EsbocoPa", "coincident", 1, second_geometry=2,
                      first_position="start", second_position="end")
            await geo(d, "EsbocoPa", "coincident", 1, second_geometry=3,
                      first_position="end", second_position="start")
            await geo(d, "EsbocoPa", "coincident", 0, second_geometry=3,
                      first_position="end", second_position="end")
            for g, pos in ((0, "start"), (0, "end"), (1, "start"), (1, "end")):
                await geo(d, "EsbocoPa", "point_on_object", g,
                          first_position=pos, second_geometry=-1)
            await geo(d, "EsbocoPa", "concentric", 0, second_geometry=1)
            await geo(d, "EsbocoPa", "point_on_object", 0,
                      first_position="center", second_geometry=-1)
            await dim(d, "EsbocoPa", "radius", 0, PA_R, "pa_raio_externo")
            await dim(d, "EsbocoPa", "radius", 1, inner_r, "pa_raio_interno")
            await dim(d, "EsbocoPa", "distance", -1, PA_CENTRO,
                      position="start", second_geometry=0,
                      second_position="center", name="pa_posicao")
            await assert_zero_dof(d, "EsbocoPa")
            # Expressoes 100% em comprimentos: literal adimensional menos
            # parametro de comprimento invalida o recompute do FreeCAD.
            for constraint, expression in (
                ("pa_raio_externo", "Params.pa_raio"),
                ("pa_raio_interno", "Params.pa_raio - Params.espessura_pa"),
                ("pa_posicao", "Params.pa_centro"),
            ):
                await d.modify(
                    "cad.bind_sketch_datum",
                    {"sketch": "EsbocoPa", "constraint": constraint,
                     "expression": expression},
                )
            await d.modify(
                "cad.add_pad",
                {"sketch": "EsbocoPa", "length": 90, "name": "PadPa"},
            )
            await d.modify(
                "cad.bind_feature_parameter",
                {"feature": "PadPa", "parameter": "length",
                 "expression": "Params.altura_pas"},
            )
            await d.modify(
                "cad.add_polar_pattern",
                {"features": ["PadPa"], "angle": 360, "occurrences": 3,
                 "axis": "z", "name": "Pas"},
            )
            print("[3] tres pas em S por padrao polar, perfil 0 DoF")

            # --- Money shots no Body (a fusao booleana e estatica: ------
            # mudancas de parametro nao repropagam por ela, entao o
            # rolamento so entra depois das dimensoes finais) --------------
            await d.modify(
                "cad.set_master_parameter",
                {"name": "altura_pas", "value": 120, "kind": "length"},
            )
            measured = await d.read("cad.measure_object", {"object": "Rotor"})
            expected = rotor_body_volume(120, PA_PAREDE, 6)
            assert close(expected, measured["volume_mm3"]), (
                expected, measured["volume_mm3"])
            print(f"[4] altura_pas=120 recalculou as tres pas: "
                  f"{expected:.1f} mm3")

            await d.modify(
                "cad.set_master_parameter",
                {"name": "espessura_pa", "value": 3.2, "kind": "length"},
            )
            validation = await d.read("cad.validate_document", {})
            assert validation["valid"] is True, validation
            measured = await d.read("cad.measure_object", {"object": "Rotor"})
            expected = rotor_body_volume(120, 3.2, 6)
            assert close(expected, measured["volume_mm3"]), (
                expected, measured["volume_mm3"])
            print(f"[5] espessura_pa=3.2 engrossou as pas: {expected:.1f} mm3")
            REPORT["criteria"].update(
                esbocos_0dof=True, parametros_recalculam=True,
            )

            # --- Rolamento print-in-place fundido no cubo ---------------
            bearing = await d.modify(
                "cad.create_print_in_place_roller_bearing",
                {"bore_diameter": 10, "outer_diameter": 34, "width": 8,
                 "roller_count": 8, "roller_diameter": 5,
                 "print_clearance": 0.4, "axial_clearance": 1.6,
                 "name": "Rolamento"},
            )
            REPORT[ROLAMENTO_VOL_KEY] = bearing["volume_mm3"]
            await d.modify(
                "cad.boolean_operation",
                {"left": "Rotor", "right": "Rolamento", "operation": "fuse",
                 "name": "RotorCompleto"},
            )
            measured = await d.read(
                "cad.measure_object", {"object": "RotorCompleto"}
            )
            expected = rotor_volume(120, 3.2, 6, bearing["volume_mm3"])
            assert close(expected, measured["volume_mm3"]), (
                expected, measured["volume_mm3"])
            print(f"[6] rolamento PIP fundido: {expected:.1f} mm3 exatos")

            # --- Base com pino chanfrado --------------------------------
            await d.modify("cad.create_body", {"name": "Base"})
            await d.modify(
                "cad.create_body_sketch",
                {"body": "Base", "plane": "xy", "name": "EsbocoBase"},
            )
            await d.modify(
                "cad.add_sketch_circle",
                {"sketch": "EsbocoBase", "center_x": 0, "center_y": 0,
                 "radius": 80},
            )
            await dim(d, "EsbocoBase", "radius", 0, 80, "base_raio",
                      "Params.diametro_base / 2")
            await geo(d, "EsbocoBase", "concentric", 0, second_geometry=-1)
            await assert_zero_dof(d, "EsbocoBase")
            await d.modify(
                "cad.add_pad",
                {"sketch": "EsbocoBase", "body": "Base", "length": 6,
                 "name": "PadBase"},
            )
            await d.modify(
                "cad.bind_feature_parameter",
                {"feature": "PadBase", "parameter": "length",
                 "expression": "Params.espessura_base"},
            )
            await d.modify(
                "cad.create_face_sketch",
                {"body": "Base",
                 "face": {"kind": "largest_planar_face", "normal": "+z"},
                 "name": "EsbocoPino"},
            )
            await d.modify(
                "cad.add_sketch_circle",
                {"sketch": "EsbocoPino", "center_x": 0, "center_y": 0,
                 "radius": 4.8},
            )
            await dim(d, "EsbocoPino", "radius", 0, 4.8, "pino_raio",
                      "Params.pino_diametro / 2")
            await geo(d, "EsbocoPino", "concentric", 0, second_geometry=-1)
            await assert_zero_dof(d, "EsbocoPino")
            await d.modify(
                "cad.add_pad",
                {"sketch": "EsbocoPino", "body": "Base", "length": 28,
                 "name": "PadPino"},
            )
            await d.modify(
                "cad.bind_feature_parameter",
                {"feature": "PadPino", "parameter": "length",
                 "expression": "Params.pino_altura"},
            )
            await d.modify(
                "cad.add_chamfer",
                {"body": "Base",
                 "edges": {"kind": "circular_edges", "diameter": 9.6},
                 "size": 3, "name": "PontaPino"},
            )
            base_ready = await d.read(
                "cad.analyze_print_readiness", {"object": "Base"}
            )
            assert base_ready["needs_support"] is False, base_ready
            print("[7] base com pino chanfrado, imprime sem suporte")

            rotor_ready = await d.read(
                "cad.analyze_print_readiness", {"object": "RotorCompleto"}
            )
            REPORT["rotor_print"] = {
                "floating_rollers": len(rotor_ready["floating_solids"]),
                "overhang_faces": len(rotor_ready["overhang_faces"]),
                "nota": "roletes flutuam por projeto no print-in-place",
            }
            print(f"[8] rotor: {len(rotor_ready['floating_solids'])} roletes "
                  "flutuantes por projeto (print-in-place)")

            # --- Montagem: rotor sobre o pino ---------------------------
            await d.modify(
                "cad.transform_object", {"object": "RotorCompleto", "z": 9.5}
            )
            fit = await d.read(
                "cad.analyze_interferences",
                {"objects": ["RotorCompleto", "Base"]},
            )
            assert fit["interference_count"] == 0, fit
            pair = fit["pairs"][0]
            assert pair["minimum_distance_mm"] > 0.15, pair
            REPORT["encaixe"] = pair
            print(f"[9] montada sem colisao; folga radial "
                  f"{pair['minimum_distance_mm']:.3f} mm")

            REPORT["criteria"].update(
                encaixe_com_folga=True, base_sem_suporte=True,
            )

            masses = {}
            for label, obj in (("rotor", "RotorCompleto"), ("base", "Base")):
                mass = await d.read(
                    "cad.measure_mass_properties",
                    {"object": obj, "density": 1.24},
                )
                masses[label] = round(mass["mass_g"], 1)
            REPORT["massas_pla_g"] = masses
            print(f"[10] massas PLA: {masses}")

            captures = await d.read(
                "cad.capture_views",
                {"views": ["isometric", "top", "front"], "width": 1200,
                 "height": 900, "fit": True},
            )
            section = await d.read(
                "cad.capture_section_view",
                {"plane": "xz", "offset": 0, "width": 1200, "height": 900},
            )
            REPORT["captures"] = [
                c["resource_uri"] for c in captures["captures"]
            ] + [section["resource_uri"]]

            snapshot = json.loads(text_of(await session.call_tool(
                "get_mcp_performance_snapshot", {}
            )))
            REPORT["mutations"] = d.mutations
            REPORT["reads"] = d.reads
            REPORT["telemetry_resumo"] = {
                "bridge_calls": snapshot["bridge"]["calls"],
                "bridge_ms": round(snapshot["bridge"]["duration_ms"]),
                "gui_exec_ms": round(snapshot["bridge"]["gui_execution_ms"]),
                "payload_bytes": snapshot["mcp"]["input_bytes"]
                + snapshot["mcp"]["output_bytes"],
            }
            out = OUT_DIR / "relatorio.json"
            out.write_text(
                json.dumps(REPORT, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            print(f"[11] relatorio gravado em {out}")
            print(f"RESUMO: {d.mutations} mutacoes, {d.reads} leituras")
            print("SAVONIUS_OK")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    asyncio.run(main())
