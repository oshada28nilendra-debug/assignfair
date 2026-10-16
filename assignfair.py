"""Offline lab allocation: maximum cardinality, then minimum preference cost."""
import argparse
import html
import json
from pathlib import Path


def validate(data):
    if not isinstance(data, dict) or set(data) != {'sessions', 'students'}:
        raise ValueError('input must contain sessions and students')
    sessions, students = data['sessions'], data['students']
    if not isinstance(sessions, dict) or not sessions:
        raise ValueError('sessions must be a nonempty name:capacity mapping')
    for name, cap in sessions.items():
        if not isinstance(name, str) or not name.strip() or type(cap) is not int or cap < 0:
            raise ValueError('session names must be nonempty and capacities nonnegative integers')
    if not isinstance(students, list):
        raise ValueError('students must be a list')
    seen = set()
    for s in students:
        if not isinstance(s, dict) or set(s) != {'id', 'available', 'preferences'}:
            raise ValueError('each student needs id, available and preferences')
        if not isinstance(s['id'], str) or not s['id'].strip() or s['id'] in seen:
            raise ValueError('student IDs must be unique nonempty strings')
        seen.add(s['id'])
        for key in ('available', 'preferences'):
            values = s[key]
            if not isinstance(values, list) or any(not isinstance(x, str) or x not in sessions for x in values):
                raise ValueError('availability/preferences must list known session names')
            if len(values) != len(set(values)):
                raise ValueError('duplicate availability/preference entry')
        if set(s['available']) != set(s['preferences']):
            raise ValueError('preferences must rank every available session exactly once')
    return sessions, students


def summarize(data, assignment, method):
    sessions, students = validate(data)
    usage = {name: 0 for name in sessions}
    rows, unmet, cost = [], [], 0
    for s in students:
        name = assignment.get(s['id'])
        rank = s['preferences'].index(name) if name is not None else None
        rows.append(dict(student=s['id'], session=name, preference_cost=rank))
        if name is not None:
            usage[name] += 1
            cost += rank
        else:
            reason = ('no_available_session' if not s['available'] else
                      'all_available_sessions_have_zero_capacity' if all(sessions[x] == 0 for x in s['available']) else
                      'capacity_competition')
            unmet.append(dict(student=s['id'], reason=reason, available=s['available']))
    return dict(method=method, assigned=len(students)-len(unmet), unassigned=len(unmet),
                preference_cost=cost, assignments=rows, unmet_demand=unmet,
                sessions=[dict(session=n, capacity=c, used=usage[n]) for n, c in sessions.items()])


def greedy(data):
    sessions, students = validate(data)
    remaining, assignment = dict(sessions), {}
    for s in students:
        for name in s['preferences']:
            if remaining[name]:
                assignment[s['id']] = name
                remaining[name] -= 1
                break
    return summarize(data, assignment, 'greedy_input_order')


def optimize(data):
    sessions, students = validate(data)
    # source -> students -> available sessions -> sink; unit student flow.
    names = list(sessions)
    source, offset = 0, 1 + len(students)
    sink = offset + len(names)
    graph = [[] for _ in range(sink + 1)]
    def edge(u, v, cap, cost):
        forward = [v, len(graph[v]), cap, cost]
        reverse = [u, len(graph[u]), 0, -cost]
        graph[u].append(forward)
        graph[v].append(reverse)
        return forward
    links = []
    for i, s in enumerate(students):
        edge(source, i+1, 1, 0)
        for rank, name in enumerate(s['preferences']):
            e = edge(i+1, offset+names.index(name), 1, rank)
            links.append((s['id'], name, e))
    for j, name in enumerate(names):
        edge(offset+j, sink, sessions[name], 0)
    while True:
        # Bellman-Ford accommodates negative-cost reverse edges after rerouting.
        dist, parent = [float('inf')]*len(graph), [None]*len(graph)
        dist[source] = 0
        for _ in range(len(graph)-1):
            changed = False
            for u, edges in enumerate(graph):
                if dist[u] == float('inf'):
                    continue
                for k, e in enumerate(edges):
                    v, _, capacity, cost = e
                    if capacity and dist[u]+cost < dist[v]:
                        dist[v], parent[v] = dist[u]+cost, (u, k)
                        changed = True
            if not changed:
                break
        if parent[sink] is None:
            break
        v = sink
        while v != source:
            u, k = parent[v]
            e = graph[u][k]
            e[2] -= 1
            graph[v][e[1]][2] += 1
            v = u
    assignment = {sid: name for sid, name, e in links if e[2] == 0}
    return summarize(data, assignment, 'min_cost_max_flow')


def compare(data):
    optimal, baseline = optimize(data), greedy(data)
    return dict(schema_version=1, objective='maximize assigned count, then minimize sum of zero-based preference ranks',
                optimized=optimal, greedy=baseline,
                comparison=dict(additional_assignments=optimal['assigned']-baseline['assigned'],
                                preference_cost_reduction_at_equal_count=(baseline['preference_cost']-optimal['preference_cost']) if optimal['assigned']==baseline['assigned'] else None))


def render(report):
    esc = lambda x: html.escape(str(x))
    out = ['<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>AssignFair</title><style>body{font:16px system-ui;max-width:1050px;margin:30px auto;padding:20px;background:#f5f2ea;color:#26342a}section{background:#fffdf8;padding:24px;margin:24px 0;border-radius:16px}table{border-collapse:collapse;width:100%}td,th{padding:10px;border-bottom:1px solid #ddd;text-align:left}.scroll{overflow:auto}h1{font-size:40px}small{color:#586456}</style><h1>AssignFair</h1><p>'+esc(report['objective'])+'</p><small>This objective does not guarantee universal or individual fairness. Review assignments before using them.</small>']
    for key in ('optimized', 'greedy'):
        r = report[key]
        out.append(f'<section><h2>{esc(r["method"])}</h2><p>Assigned: {r["assigned"]} · Unassigned: {r["unassigned"]} · Preference cost: {r["preference_cost"]}</p><div class="scroll"><table><tr><th>Student</th><th>Session</th><th>Cost (rank − 1)</th></tr>')
        for a in r['assignments']:
            out.append('<tr>'+''.join('<td>'+esc(a[k] if a[k] is not None else 'Unassigned')+'</td>' for k in ('student','session','preference_cost'))+'</tr>')
        out.append('</table></div><h3>Capacity use</h3><ul>')
        for s in r['sessions']:
            out.append(f'<li>{esc(s["session"])}: {s["used"]} / {s["capacity"]}</li>')
        out.append('</ul><h3>Unmet demand</h3><ul>')
        for u in r['unmet_demand']:
            out.append('<li>'+esc(u['student'])+': '+esc(u['reason'])+'; available '+esc(u['available'])+'</li>')
        out.append('</ul></section>')
    return ''.join(out)+'</html>'


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('input', type=Path)
    p.add_argument('--out', type=Path, required=True, help='new directory for JSON and HTML')
    a = p.parse_args()
    try:
        report = compare(json.loads(a.input.read_text(encoding='utf-8')))
        a.out.mkdir(parents=True, exist_ok=False)
        (a.out/'report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
        (a.out/'index.html').write_text(render(report), encoding='utf-8')
        print(json.dumps({k:{x:report[k][x] for x in ('assigned','unassigned','preference_cost')} for k in ('optimized','greedy')}, indent=2))
    except (ValueError, OSError) as e:
        p.exit(2, f'Error: {e}\n')

if __name__ == '__main__':
    main()
