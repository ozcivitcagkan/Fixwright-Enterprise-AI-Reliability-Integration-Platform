from langchain_core.tools import tool


def make_tools(conn):
    @tool
    def get_incident(incident_id: str) -> dict:
        """Fetch a single incident by its incident_id, for example INC-101.
        Returns the incident's description, or an error if it does not exist."""
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT incident_id, description
                FROM incidents
                WHERE incident_id = %s
                ORDER BY id DESC
                LIMIT 1
                """,
                (incident_id,),
            )
            row = cursor.fetchone()

        if row is None:
            return {"error": f"No incident found with incident_id {incident_id}"}

        return {"incident_id": row[0], "description": row[1]}

    @tool
    def search_similar_incidents(
        keywords: str,
        exclude_incident_id: str | None = None,
        limit: int = 5,
    ) -> list[dict]:
        """Find past incidents whose description contains any of the given keywords.
        Pass a few space-separated keywords, for example "database timeout payroll".
        Use exclude_incident_id to leave out the incident you are analyzing."""
        words = [word for word in keywords.lower().split() if len(word) >= 3]
        if not words:
            return []

        patterns = [f"%{word}%" for word in words]
        sql = """
            SELECT incident_id, description
            FROM incidents
            WHERE description ILIKE ANY(%s)
        """
        params = [patterns]

        if exclude_incident_id:
            sql += " AND incident_id <> %s"
            params.append(exclude_incident_id)

        sql += " ORDER BY id DESC LIMIT %s"
        params.append(min(limit, 10))

        with conn.cursor() as cursor:
            cursor.execute(sql, params)
            rows = cursor.fetchall()

        return [{"incident_id": row[0], "description": row[1]} for row in rows]

    return [get_incident, search_similar_incidents]