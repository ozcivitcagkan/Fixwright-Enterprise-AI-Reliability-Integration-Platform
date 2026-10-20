def create_incident(client, incident_id="INC-001", description="Database timeout"):
    return client.post(
        "/incidents",
        json={"incident_id": incident_id, "description": description},
    )


def test_create_incident_returns_created_data(client):
    response = create_incident(client)

    assert response.status_code == 200
    assert response.json()["incident_id"] == "INC-001"
    assert response.json()["description"] == "Database timeout"


def test_get_incidents_returns_created_incident(client):
    create_incident(client)

    response = client.get("/incidents")

    assert response.status_code == 200
    assert response.json() == [
        {"id": 1, "incident_id": "INC-001", "description": "Database timeout"}
    ]


def test_update_incident_changes_description(client):
    create_incident(client)

    response = client.put(
        "/incidents/INC-001",
        json={"description": "Resolved by restarting the job"},
    )

    assert response.status_code == 200
    incidents = client.get("/incidents").json()
    assert incidents[0]["description"] == "Resolved by restarting the job"


def test_update_unknown_incident_returns_404(client):
    response = client.put(
        "/incidents/DOES-NOT-EXIST",
        json={"description": "Anything"},
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Incident not found"}


def test_delete_incident_removes_it(client):
    create_incident(client)

    response = client.delete("/incidents/INC-001")

    assert response.status_code == 200
    assert client.get("/incidents").json() == []


def test_delete_unknown_incident_returns_404(client):
    response = client.delete("/incidents/DOES-NOT-EXIST")

    assert response.status_code == 404


def test_create_incident_without_description_returns_422(client):
    response = client.post("/incidents", json={"incident_id": "INC-001"})

    assert response.status_code == 422
    


def test_create_duplicate_incident_returns_409(client):
    create_incident(client)

    response = create_incident(client)

    assert response.status_code == 409
    assert response.json() == {"detail": "Incident already exists"}


def test_create_incident_with_blank_description_returns_422(client):
    response = create_incident(client, description="   ")

    assert response.status_code == 422