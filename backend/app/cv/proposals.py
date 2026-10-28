def is_conflict(p, graph):
    s, o = p.subject_id, p.object_id
    if s in graph.objects(o, "part_of"):
        return True
    if p.predicate == "part_of":
        parents = graph.objects(s, "part_of")
        return bool(parents) and o not in parents
    return o in graph.objects(s, "part_of")


def save_proposals(proposals, graph, db):
    saved = 0
    for p in proposals:
        if p.object_id in graph.objects(p.subject_id, p.predicate):
            continue
        p.conflict = is_conflict(p, graph)
        db.merge(p)
        saved += 1
    db.commit()
    return saved
