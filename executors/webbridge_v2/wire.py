"""Compact graph wire v1. Expansion is bounded and then subjected to full graph validation."""
import json


def expand_graph(raw: dict) -> dict:
    if not isinstance(raw, dict) or set(raw) != {'wire_version', 'header', 'nodes', 'relations', 'resolutions', 'unresolved'} or type(raw['wire_version']) is not int or raw['wire_version'] != 1:
        raise ValueError('V2_WIRE_INVALID')
    if len(json.dumps(raw, separators=(',', ':')).encode()) > 32000:
        raise ValueError('V2_WIRE_BOUND')
    if type(raw['header']) is not dict or set(raw['header']) & {'nodes', 'relations', 'resolutions', 'unresolved', 'evidence'}:
        raise ValueError('V2_WIRE_INVALID')
    for key, maximum, width in [('nodes', 512, 13), ('relations', 1024, 4), ('resolutions', 1024, 4), ('unresolved', 1024, 4)]:
        if type(raw[key]) is not list or len(raw[key]) > maximum or any(type(row) is not list or len(row) != width for row in raw[key]):
            raise ValueError('V2_WIRE_INVALID')
    graph = dict(raw['header'])
    nodes, evidence = [], []
    for i, row in enumerate(raw['nodes']):
        node_id, parent, tag, role, name, conflict, route, selected, expanded, control, attributes, visibility, metadata = row
        if type(visibility) is not list or len(visibility) != 4 or type(metadata) is not list or len(metadata) != 2:
            raise ValueError('V2_WIRE_INVALID')
        eid = f'e{i + 1}'
        nodes.append(dict(id=node_id, parent=parent, tag=tag, role=role, name=name, name_conflict=conflict,
            current_route=route, selected=selected, expanded=expanded, control=control, attributes=attributes,
            visible=visibility[0] == 'VISIBLE', visibility=dict(zip(['layout', 'accessibility', 'viewport', 'paint'], visibility, strict=True)),
            action_effect='UNKNOWN', metadata_name=dict(token=name, classification='CONFLICTING' if conflict else 'APPROVED_STATIC' if name else 'UNCLASSIFIED',
                source_nodes=metadata[0], relation_refs=metadata[1], evidence_refs=[eid])))
        evidence.append(dict(id=eid, source='PROVIDER_DOM', claim='NODE_METADATA', nodes=[node_id],
            algorithm='metadata-projector-2', observation_id=graph.get('observation_id')))
    graph.update(nodes=nodes, evidence=evidence,
        relations=[dict(zip(['id', 'from', 'to', 'kind'], r, strict=True)) for r in raw['relations']],
        unresolved=[dict(zip(['from', 'kind', 'status', 'candidate_count'], r, strict=True)) for r in raw['unresolved']],
        resolutions=[dict(zip(['from', 'kind', 'status', 'candidates'], r, strict=True), candidate_count=len(r[3])) for r in raw['resolutions']])
    return graph
