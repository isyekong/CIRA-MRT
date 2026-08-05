#!/usr/bin/env python3
"""Apply the nearest-operator-anchor customer-cone fix to the main script.

This helper is intentionally strict: every replacement must match the expected
main-branch source exactly. It is used once by the validation workflow because
this environment cannot push a normal local git patch directly.
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "mrt_cn_routes.py"
README = ROOT / "README.md"
MARKER = "OPERATOR_ANCHOR_FAMILY"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly one match, found {count}")
    return text.replace(old, new, 1)


def patch_script() -> bool:
    text = SCRIPT.read_text(encoding="utf-8")
    if MARKER in text:
        print("mrt_cn_routes.py already contains the operator-anchor fix")
        return False

    old_groups = '''# Two tiers, distinguished by name and origin gate:
#   "China"  tables (gate = cn_origin)     -> mainland only: ORIGIN AS must be
#            China-registered. No international customers.
#   "Global" tables (gate = customer_cone) -> operator + international customers:
#            ORIGIN AS in the operator's CAIDA customer cone (peers/upstreams it
#            merely transits are excluded), unioned with CN origins for
#            completeness.
# Keys ending in _global are the Global tier; the rest are the China tier.
GROUPS = {
    # --- China tier (mainland, CN origin) --------------------------------
    "chinatelecom": {
        "name": "China Telecom (China)",
        "asns": [4134],
        "gate": "cn_origin",
    },
    "chinaunicom": {
        "name": "China Unicom (China)",
        "asns": [4837, 9929],
        "gate": "cn_origin",
    },
    "chinamobile": {
        "name": "China Mobile (China)",
        "asns": [9808],
        "gate": "cn_origin",
    },
    "cernet_edu": {
        "name": "Education & Research Network (China)",
        "asns": [4538, 23911, 7497],
        "gate": "cn_origin",
    },
    "china_domestic_all": {
        "name": "China Domestic (China)",
        "asns": [4134, 4837, 9929, 9808, 4538, 23911, 7497, 146762],
        "gate": "cn_origin",
    },
    # --- Global tier (incl. international customers, customer cone) -------
    "chinatelecom_global": {
        "name": "China Telecom (Global)",
        "asns": [4134, 4809, 23764],
        "gate": "customer_cone",
    },
    "chinaunicom_global": {
        "name": "China Unicom (Global)",
        "asns": [4837, 9929, 10099],
        "gate": "customer_cone",
    },
    "chinamobile_global": {
        "name": "China Mobile (Global)",
        "asns": [9808, 58453, 58807, 268862, 137872, 209141, 9231, 135054, 328787, 132389, 139619, 141419],
        "gate": "customer_cone",
    },
    "china_all_global": {
        "name": "China All (Global)",
        "asns": list(ASN_MAP.keys()),
        "gate": "customer_cone",
    },
}
'''
    new_groups = '''# Two tiers, both using per-route provider->customer validation:
#   "China"  tables require a CN-registered origin AND a verified downstream
#            chain from the nearest operator anchor to the origin.
#   "Global" tables require the same verified downstream chain, without a
#            country restriction. CN registration alone never proves that an
#            origin is a customer's network.
#
# ``family`` identifies only operator-owned anchor ASNs. Customer/provincial
# ASNs are deliberately not hard-coded; they are discovered from CAIDA p2c
# relationships along each route's actual AS_PATH.
GROUPS = {
    # --- China tier (mainland downstream customer cone) -------------------
    "chinatelecom": {
        "name": "China Telecom (China)",
        "asns": [4134],
        "family": "chinatelecom",
        "gate": "domestic_customer_cone",
    },
    "chinaunicom": {
        "name": "China Unicom (China)",
        "asns": [4837, 9929],
        "family": "chinaunicom",
        "gate": "domestic_customer_cone",
    },
    "chinamobile": {
        "name": "China Mobile (China)",
        "asns": [9808],
        "family": "chinamobile",
        "gate": "domestic_customer_cone",
    },
    "cernet_edu": {
        "name": "Education & Research Network (China)",
        "asns": [4538, 23911, 7497],
        "family": "cernet_edu",
        "gate": "domestic_customer_cone",
    },
    "china_domestic_all": {
        "name": "China Domestic (China)",
        "asns": [4134, 4837, 9929, 9808, 4538, 23911, 7497, 146762],
        "aggregate": True,
        "gate": "domestic_customer_cone",
    },
    # --- Global tier (incl. international downstream customers) -----------
    "chinatelecom_global": {
        "name": "China Telecom (Global)",
        "asns": [4134, 4809, 23764],
        "family": "chinatelecom",
        "gate": "customer_cone",
    },
    "chinaunicom_global": {
        "name": "China Unicom (Global)",
        "asns": [4837, 9929, 10099],
        "family": "chinaunicom",
        "gate": "customer_cone",
    },
    "chinamobile_global": {
        "name": "China Mobile (Global)",
        "asns": [9808, 58453, 58807, 268862, 137872, 209141, 9231, 135054, 328787, 132389, 139619, 141419],
        "family": "chinamobile",
        "gate": "customer_cone",
    },
    "china_all_global": {
        "name": "China All (Global)",
        "asns": list(ASN_MAP.keys()),
        "aggregate": True,
        "gate": "customer_cone",
    },
}

# Build the anchor map from operator-owned ASNs already declared in GROUPS.
# This is not a customer list: downstream ASNs remain entirely data-driven.
OPERATOR_FAMILY_ASNS: dict[str, set[int]] = {}
for _group in GROUPS.values():
    _family = _group.get("family")
    if _family:
        OPERATOR_FAMILY_ASNS.setdefault(_family, set()).update(_group["asns"])

OPERATOR_ANCHOR_FAMILY: dict[int, str] = {}
for _family, _asns in OPERATOR_FAMILY_ASNS.items():
    for _asn in _asns:
        _previous = OPERATOR_ANCHOR_FAMILY.setdefault(_asn, _family)
        if _previous != _family:
            raise ValueError(f"operator anchor AS{_asn} belongs to multiple families")
'''
    text = replace_once(text, old_groups, new_groups, "GROUPS block")

    old_path_function = '''def path_customer_chain_ok(seq: list[int], seeds, p2c: dict) -> bool:
    """True if the origin sits in an operator seed's customer cone ALONG THIS path.

    ``seq`` is the ordered AS_PATH (see :func:`_ordered_seq`). For every position
    ``i`` where ``seq[i]`` is an operator seed, every later hop toward the origin
    must be provider->customer: ``seq[j+1]`` must be a customer of ``seq[j]``
    (``seq[j+1] in p2c[seq[j]]``). A peer or upstream hop breaks the chain.
    Returns True as soon as one seed yields an unbroken chain to the origin (a
    seed that itself originates the prefix trivially qualifies).

    Direction matters: an edge is only valid provider->customer. If the seed is
    a *customer* of the next hop (customer->provider, i.e. an uphill link), the
    chain breaks -- so a prefix reached via the operator's upstream is rejected
    even though a relationship exists between the two ASes.
    """
    n = len(seq)
    for i in range(n):
        if seq[i] not in seeds:
            continue
        ok = True
        for j in range(i, n - 1):
            customers = p2c.get(seq[j])
            if not customers or seq[j + 1] not in customers:
                ok = False
                break
        if ok:
            return True
    return False
'''
    new_path_function = old_path_function + '''

def nearest_operator_anchor(
    seq: list[int],
    anchor_families: dict[int, str] = OPERATOR_ANCHOR_FAMILY,
) -> tuple[Optional[str], Optional[int]]:
    """Return the operator family and index nearest to the route origin.

    Searching from right to left prevents an upstream/peer operator earlier in
    the path from claiming another operator and its entire customer cone. For
    example ``4837 9808 24445`` is anchored to China Mobile (9808), not Unicom.
    """
    for index in range(len(seq) - 1, -1, -1):
        family = anchor_families.get(seq[index])
        if family is not None:
            return family, index
    return None, None


def customer_chain_from_index_ok(seq: list[int], anchor_index: Optional[int],
                                 p2c: dict) -> bool:
    """Validate every hop from one selected anchor to the origin as p2c."""
    if anchor_index is None or anchor_index < 0 or anchor_index >= len(seq):
        return False
    for index in range(anchor_index, len(seq) - 1):
        customers = p2c.get(seq[index])
        if not customers or seq[index + 1] not in customers:
            return False
    return True


def has_ambiguous_as_set(as_path) -> bool:
    """True when an AS_SET prevents deterministic per-hop ownership."""
    return any(seg.kind == "SET" for seg in normalize_as_path(as_path))


def classify_operator_customer_path(
    seq: list[int],
    p2c: dict,
    anchor_families: dict[int, str] = OPERATOR_ANCHOR_FAMILY,
) -> Optional[str]:
    """Classify a route by its nearest anchor after strict p2c validation."""
    family, anchor_index = nearest_operator_anchor(seq, anchor_families)
    if family is None:
        return None
    if not customer_chain_from_index_ok(seq, anchor_index, p2c):
        return None
    return family
'''
    text = replace_once(text, old_path_function, new_path_function, "path helpers")

    old_flush = '''def flush_route(
    record: RouteRecord,
    groups: dict,
    group_buffers: dict,
    stats: Stats,
    cn_asns: Iterable[int] = CN_PATH_FILTER_ASNS,
    t1_asns: Iterable[int] = T1_ASNS,
    group_gates: Optional[dict] = None,
) -> None:
    """Apply matching + filtering for a single route and buffer prefixes.

    * Increments ``total_raw_routes_seen``.
    * Validates the prefix; invalid ones are counted and skipped.
    * Matches groups by AS_PATH membership (a route is grouped under an operator
      if that operator's ASN appears anywhere in the path -- this keeps prefixes
      originated by the operator's provincial/child ASNs that only transit the
      backbone).
    * Computes the CN->T1 verdict once (route-level).
    * PER-GROUP GATE (if ``group_gates`` given): each matched group applies its
      own gate spec before receiving the prefix. A ``cn`` spec (China tier) keeps
      the prefix only when the ORIGIN AS is CN-registered. A ``cone`` spec
      (Global tier) keeps it when the origin is CN-registered (rule 2) OR the
      origin is reachable from an operator seed through a valley-free
      provider->customer chain ON THIS AS_PATH (rule 1) -- so a prefix reached
      only via the operator's peer/upstream (e.g. AS3462 via China Telecom, or a
      customer of the operator's peer) is kept out.
    """
    stats.total_raw_routes_seen += 1

    if not record.as_path:
        return

    try:
        ipaddress.ip_network(record.prefix, strict=False)
    except Exception:
        stats.invalid_prefixes += 1
        return

    all_asns = as_path_all_asns(record.as_path)
    if not all_asns:
        return

    # Which groups does this route match (membership only)?
    matched_groups = [
        key for key, g in groups.items()
        if not set(g["asns"]).isdisjoint(all_asns)
    ]
    if not matched_groups:
        return

    cn_to_t1 = is_cn_to_t1_path(record.as_path, cn_asns, t1_asns)
    if cn_to_t1:
        stats.total_filtered_cn_to_t1 += 1
        return

    origins = route_origin_asns(record.as_path) if group_gates else None
    ordered = None  # AS_PATH flattened on demand for customer_cone groups
    version_key = "v4" if record.ip_version == 4 else "v6"
    added_any = False
    for key in matched_groups:
        spec = group_gates.get(key) if group_gates else None
        if spec is not None and origins is not None:
            if spec["kind"] == "cn":
                # China tier: origin must be a CN-registered ASN.
                if origins.isdisjoint(_GATE_CN):
                    continue
            else:  # "cone" -- Global tier
                # Keep if the origin is CN-registered (rule 2: CAIDA may miss it)
                # OR reachable from an operator seed via a valley-free
                # provider->customer chain on THIS path (rule 1). This excludes
                # prefixes reached only over a peer/upstream link.
                if origins.isdisjoint(_GATE_CN):
                    if ordered is None:
                        ordered = _ordered_seq(record.as_path)
                    if not path_customer_chain_ok(ordered, spec["seeds"], _GATE_P2C):
                        continue
        # Buffers are sets: a prefix seen via many peers is stored once.
        group_buffers[key][version_key].add(record.prefix)
        added_any = True

    if added_any:
        stats.total_matched_routes += 1
    else:
        # Matched by membership but gated out of every table (e.g. foreign
        # origin / outside the customer cone).
        stats.total_filtered_foreign_origin += 1
'''
    new_flush = '''def flush_route(
    record: RouteRecord,
    groups: dict,
    group_buffers: dict,
    stats: Stats,
    cn_asns: Iterable[int] = CN_PATH_FILTER_ASNS,
    t1_asns: Iterable[int] = T1_ASNS,
    group_gates: Optional[dict] = None,
) -> None:
    """Apply route matching and strict operator-customer ownership gates.

    AS_PATH membership remains a cheap candidate filter. Final ownership is
    determined by the operator anchor nearest to the origin, followed by a
    strict provider->customer check for every remaining hop. This retains
    dynamically discovered downstream customers while preventing paths such as
    ``4837 9808 24445`` from placing Mobile prefixes in Unicom's lists.
    """
    stats.total_raw_routes_seen += 1

    if not record.as_path:
        return

    try:
        ipaddress.ip_network(record.prefix, strict=False)
    except Exception:
        stats.invalid_prefixes += 1
        return

    all_asns = as_path_all_asns(record.as_path)
    if not all_asns:
        return

    matched_groups = [
        key for key, group in groups.items()
        if not set(group["asns"]).isdisjoint(all_asns)
    ]
    if not matched_groups:
        return

    if is_cn_to_t1_path(record.as_path, cn_asns, t1_asns):
        stats.total_filtered_cn_to_t1 += 1
        return

    origins = route_origin_asns(record.as_path) if group_gates else None
    ordered: Optional[list[int]] = None
    owner_family: Optional[str] = None
    owner_evaluated = False
    version_key = "v4" if record.ip_version == 4 else "v6"
    added_any = False

    for key in matched_groups:
        spec = group_gates.get(key) if group_gates else None
        if spec is not None and origins is not None:
            # Never fall back to path-only ownership when required gate data was
            # explicitly disabled or unavailable. The affected table stays empty.
            if not spec["enabled"]:
                continue
            if spec["kind"] == "domestic_cone" and origins.isdisjoint(_GATE_CN):
                continue

            # AS_SET has no deterministic order. Reject the route rather than
            # stitching sequence segments across an ambiguous path boundary.
            if has_ambiguous_as_set(record.as_path):
                continue
            if ordered is None:
                ordered = _ordered_seq(record.as_path)

            if len(origins) != 1 or not ordered or ordered[-1] not in origins:
                continue

            if not owner_evaluated:
                owner_family = classify_operator_customer_path(ordered, _GATE_P2C)
                owner_evaluated = True
            if owner_family is None:
                continue

            # Aggregate groups accept every verified operator family; specific
            # groups accept only their own nearest anchor family.
            if not spec["aggregate"] and owner_family != spec["family"]:
                continue

        group_buffers[key][version_key].add(record.prefix)
        added_any = True

    if added_any:
        stats.total_matched_routes += 1
    else:
        stats.total_filtered_foreign_origin += 1
'''
    text = replace_once(text, old_flush, new_flush, "flush_route")

    old_gates = '''def build_group_gates(groups: dict, cn_origin_asns: Optional[set],
                      p2c: Optional[dict]) -> Optional[dict]:
    """Build the per-group gate specs from each group's gate type.

      * China tier (cn_origin)     -> ``{"kind": "cn"}``: keep CN-registered
        origins only (strict; mainland, no international customers).
      * Global tier (customer_cone) -> ``{"kind": "cone", "seeds": frozenset}``:
        keep origins reachable from an operator seed via a valley-free
        provider->customer chain on the route's own AS_PATH (rule 1), UNION
        CN-registered origins (rule 2, to catch prefixes CAIDA might miss).
        Peers/upstreams merely transited are excluded.

    The heavy data (the CN set and the CAIDA provider->customer map) is NOT
    embedded here -- it lives in the ``_GATE_P2C`` / ``_GATE_CN`` module globals
    (see :func:`_init_gate_globals`) so it is never pickled per parse task. The
    ``cn`` / ``p2c`` arguments are used only to decide whether a group is gated.

    Returns None if every group ends up ungated (so gating can be skipped).
    """
    cn = cn_origin_asns or set()
    gates: dict = {}
    any_gated = False
    for key, g in groups.items():
        gate_type = g.get("gate", "none")
        if gate_type == "cn_origin":
            spec = {"kind": "cn"} if cn else None
        elif gate_type == "customer_cone":
            # Gated when either the topology (rule 1) or the CN set (rule 2) is
            # available; run() guarantees p2c is present for cone groups.
            spec = ({"kind": "cone", "seeds": frozenset(g["asns"])}
                    if (p2c or cn) else None)
        else:
            spec = None
        gates[key] = spec
        if spec is not None:
            any_gated = True
    return gates if any_gated else None
'''
    new_gates = '''def build_group_gates(groups: dict, cn_origin_asns: Optional[set],
                      p2c: Optional[dict]) -> Optional[dict]:
    """Build strict per-group ownership gates.

    Domestic groups require both CN-origin data and CAIDA p2c topology. Global
    groups require p2c topology. The gate stores only the intended operator
    family; downstream customer ASNs are inferred per route and never embedded.
    """
    cn = cn_origin_asns or set()
    gates: dict = {}
    any_gated = False
    for key, group in groups.items():
        gate_type = group.get("gate", "none")
        if gate_type == "domestic_customer_cone":
            enabled = bool(cn and p2c)
            kind = "domestic_cone"
        elif gate_type == "customer_cone":
            enabled = bool(p2c)
            kind = "global_cone"
        else:
            enabled = False
            kind = "none"

        spec = ({
            "kind": kind,
            "family": group.get("family"),
            "aggregate": bool(group.get("aggregate")),
            "enabled": enabled,
        } if gate_type in ("domestic_customer_cone", "customer_cone") else None)
        gates[key] = spec
        if spec is not None:
            any_gated = True
    return gates if any_gated else None
'''
    text = replace_once(text, old_gates, new_gates, "build_group_gates")

    text = replace_once(
        text,
        'if not args.no_origin_gate and any(g.get("gate") == "cn_origin" for g in GROUPS.values()):',
        'if not args.no_origin_gate and any(g.get("gate") == "domestic_customer_cone" for g in GROUPS.values()):',
        "origin gate load condition",
    )
    text = replace_once(
        text,
        'if not args.no_cone_gate and any(g.get("gate") == "customer_cone" for g in GROUPS.values()):',
        'if not args.no_cone_gate and any(g.get("gate") in ("domestic_customer_cone", "customer_cone") for g in GROUPS.values()):',
        "cone gate load condition",
    )

    old_log = '''            if spec["kind"] == "cn":
                LOG.info("gate[%s] = cn_origin (%d CN-registered origin ASNs)",
                         key, len(_GATE_CN))
            else:
                LOG.info("gate[%s] = customer_cone (per-path valley-free; "
                         "%d seed ASN(s), %d providers in p2c, +%d CN origins)",
                         key, len(spec["seeds"]), len(_GATE_P2C), len(_GATE_CN))
'''
    new_log = '''            LOG.info(
                "gate[%s] = %s (enabled=%s, family=%s, aggregate=%s, %d providers in p2c, %d CN origins)",
                key, spec["kind"], spec["enabled"], spec["family"], spec["aggregate"],
                len(_GATE_P2C), len(_GATE_CN),
            )
'''
    text = replace_once(text, old_log, new_log, "gate logging")

    SCRIPT.write_text(text, encoding="utf-8")
    return True


def patch_readme() -> bool:
    text = README.read_text(encoding="utf-8")
    old = '''- **China 層(`cn_origin`)**:要求 prefix 的 origin AS **註冊在中國**。CN ASN 清單
  取自**全部五個 RIR** 的 delegated-extended 統計(APNIC / RIPE / ARIN / LACNIC /
  AFRINIC),union 後篩 `cc=CN`——這樣連在 RIPE 等註冊、但國別為 CN 的 ASN 也能收到。
- **Global 層(`customer_cone`)**:要求 origin AS 在該運營商的 **CAIDA 客戶錐**內
  (operator + 各級真實客戶,含國際;peer/上游被排除),再聯集 CN origin。
'''
    new = '''- **China 層(`domestic_customer_cone`)**:origin AS 必須註冊在中國,並且從
  **距離 origin 最近的運營商錨點 ASN** 到 origin 的每一跳都必須是 CAIDA
  `provider→customer`。CN 身份只負責境內篩選,不能繞過客戶關係驗證。
- **Global 層(`customer_cone`)**:不限制 origin 國別,但同樣要求最近運營商錨點到
  origin 全程是 `provider→customer`。若 AS_PATH 同時包含多家運營商,只由距離
  origin 最近的一家認領;真實多宿主客戶仍可從不同觀測路徑分別進入多家清單。

下游、省網與 IDC ASN **不硬編碼**。程式只維護運營商自身可確認的錨點 ASN,
客戶及多級客戶完全依每條 AS_PATH 與 CAIDA p2c 關係動態判定。未知關係採 fail-closed,
不再用「origin 是 CN ASN」作兜底,避免聯通/移動/電信互相吞入對方客戶錐。
'''
    if old not in text:
        if "domestic_customer_cone" in text:
            print("README.md already contains the updated gate semantics")
            return False
        raise RuntimeError("README gate section: expected text not found")
    README.write_text(text.replace(old, new, 1), encoding="utf-8")
    return True


def main() -> int:
    changed = patch_script()
    changed = patch_readme() or changed
    print("operator-anchor fix applied" if changed else "no changes required")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
