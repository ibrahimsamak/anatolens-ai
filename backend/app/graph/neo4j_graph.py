import yaml


def load_structures_into_neo4j(driver, *paths):
    data = []
    for path in paths:
        with open(path, encoding="utf-8") as f:
            data += yaml.safe_load(f) or []
    with driver.session() as s:
        for n in data:
            s.run("MERGE (n:Structure {id:$id}) SET n.name = $en, n.name_en = $en, n.name_ar = $ar, "
                  "n.mesh_name = $mesh, n.system = $system", id=n["id"], en=n.get("display_name_en"),
                  ar=n.get("display_name_ar"), mesh=n.get("mesh_name"), system=n["id"].split(".")[0])
        for node in data:
            for rel, targets in (node.get("relations") or {}).items():
                for t in targets:
                    s.run("MATCH (a:Structure {id:$a}) MERGE (b:Structure {id:$b}) "
                          "MERGE (a)-[:REL {type:$t}]->(b)", a=node["id"], b=t, t=rel)


class Neo4jAnatomyGraph:
    def __init__(self, driver):
        self.driver = driver

    def _ids(self, query, **params):
        with self.driver.session() as s:
            return {r["id"] for r in s.run(query, **params)}

    def neighbors(self, node_id, hops=1):
        if hops < 1:
            return set()
        return self._ids(f"MATCH (a:Structure {{id:$id}})-[*1..{int(hops)}]-(b:Structure) "
                         "WHERE b.id <> $id RETURN DISTINCT b.id AS id", id=node_id)

    def objects(self, node_id, predicate):
        return self._ids("MATCH (:Structure {id:$id})-[:REL {type:$t}]->(b:Structure) "
                         "RETURN DISTINCT b.id AS id", id=node_id, t=predicate)

    def add_edge(self, subject_id, predicate, object_id):
        with self.driver.session() as s:
            s.run("MERGE (a:Structure {id:$a}) MERGE (b:Structure {id:$b}) "
                  "MERGE (a)-[:REL {type:$t}]->(b)", a=subject_id, b=object_id, t=predicate)
