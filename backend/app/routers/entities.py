"""CRUD endpoints for every entity type: /api/{researchers|papers|institutions|departments|topics|conferences|journals}."""

from typing import Optional

from fastapi import APIRouter, Query

from .. import schemas as S
from ..services import crud

router = APIRouter(prefix="/api", tags=["CRUD"])

Q = Query(None, max_length=100, description="Free-text search")
SKIP = Query(0, ge=0, le=100000)
LIMIT = Query(25, ge=1, le=200)


# ---------------------------------------------------------------- Researchers
@router.get("/researchers")
def list_researchers(q: Optional[str] = Q, specialization: Optional[str] = None, institutionId: Optional[str] = None,
                     departmentId: Optional[str] = None, skip: int = SKIP, limit: int = LIMIT):
    return crud.list_entities("researchers", q, skip, limit, {"specialization": specialization,
                              "institutionId": institutionId, "departmentId": departmentId})


@router.post("/researchers", status_code=201)
def create_researcher(body: S.ResearcherCreate):
    return crud.create_entity("researchers", body.model_dump())


@router.get("/researchers/{entity_id}")
def get_researcher(entity_id: str):
    return crud.get_entity("researchers", entity_id)


@router.put("/researchers/{entity_id}")
def update_researcher(entity_id: str, body: S.ResearcherUpdate):
    return crud.update_entity("researchers", entity_id, body.model_dump())


@router.delete("/researchers/{entity_id}")
def delete_researcher(entity_id: str):
    return crud.delete_entity("researchers", entity_id)


# ---------------------------------------------------------------- Papers
@router.get("/papers")
def list_papers(q: Optional[str] = Q, year: Optional[int] = Query(None, ge=1900, le=2100),
                researcherId: Optional[str] = None, topicId: Optional[str] = None, conferenceId: Optional[str] = None,
                journalId: Optional[str] = None, skip: int = SKIP, limit: int = LIMIT):
    return crud.list_entities("papers", q, skip, limit, {"year": year, "researcherId": researcherId, "topicId": topicId,
                              "conferenceId": conferenceId, "journalId": journalId})


@router.post("/papers", status_code=201)
def create_paper(body: S.PaperCreate):
    """Atomic: paper + authors + topics + venue + citations are created in ONE transaction.
    Any invalid reference (unknown author, newer cited paper, duplicate id/DOI) rolls everything back."""
    return crud.create_entity("papers", body.model_dump())


@router.get("/papers/{entity_id}")
def get_paper(entity_id: str):
    return crud.get_entity("papers", entity_id)


@router.put("/papers/{entity_id}")
def update_paper(entity_id: str, body: S.PaperUpdate):
    return crud.update_entity("papers", entity_id, body.model_dump())


@router.delete("/papers/{entity_id}")
def delete_paper(entity_id: str):
    return crud.delete_entity("papers", entity_id)


# ---------------------------------------------------------------- Simple entities (generated per type)
def _register(entity: str, create_model, update_model, extra_filters: tuple[str, ...] = ()):
    def list_(q: Optional[str] = Q, skip: int = SKIP, limit: int = LIMIT, institutionId: Optional[str] = None):
        filters = {"institutionId": institutionId} if "institutionId" in extra_filters else {}
        return crud.list_entities(entity, q, skip, limit, filters)

    def create(body: create_model):  # type: ignore[valid-type]
        return crud.create_entity(entity, body.model_dump())

    def get(entity_id: str):
        return crud.get_entity(entity, entity_id)

    def update(entity_id: str, body: update_model):  # type: ignore[valid-type]
        return crud.update_entity(entity, entity_id, body.model_dump())

    def delete(entity_id: str, force: bool = False):
        return crud.delete_entity(entity, entity_id, force)

    router.add_api_route(f"/{entity}", list_, methods=["GET"], name=f"list_{entity}")
    router.add_api_route(f"/{entity}", create, methods=["POST"], status_code=201, name=f"create_{entity}")
    router.add_api_route(f"/{entity}/{{entity_id}}", get, methods=["GET"], name=f"get_{entity}")
    router.add_api_route(f"/{entity}/{{entity_id}}", update, methods=["PUT"], name=f"update_{entity}")
    router.add_api_route(f"/{entity}/{{entity_id}}", delete, methods=["DELETE"], name=f"delete_{entity}")


_register("institutions", S.InstitutionCreate, S.InstitutionUpdate)
_register("departments", S.DepartmentCreate, S.DepartmentUpdate, ("institutionId",))
_register("topics", S.TopicCreate, S.TopicUpdate)
_register("conferences", S.ConferenceCreate, S.ConferenceUpdate)
_register("journals", S.JournalCreate, S.JournalUpdate)


@router.get("/next-id/{entity}", tags=["CRUD"])
def next_id(entity: str):
    return {"entity": entity, "nextId": crud.next_id(entity)}


# ---------------------------------------------------------------- Declared collaborations
@router.post("/collaborations", status_code=201, tags=["CRUD"])
def declare_collaboration(body: S.CollaborationCreate):
    return crud.declare_collaboration(body.researcherA, body.researcherB, body.since)


@router.delete("/collaborations/{researcher_a}/{researcher_b}", tags=["CRUD"])
def remove_collaboration(researcher_a: str, researcher_b: str):
    return crud.remove_collaboration(researcher_a, researcher_b)
