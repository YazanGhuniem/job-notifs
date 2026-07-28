from . import (
    amazon,
    ashby,
    eightfold,
    greenhouse,
    lever,
    microsoft,
    smartrecruiters,
    uber,
    workday,
)

REGISTRY = {
    "greenhouse": greenhouse.fetch,
    "ashby": ashby.fetch,
    "lever": lever.fetch,
    "workday": workday.fetch,
    "smartrecruiters": smartrecruiters.fetch,
    "amazon": amazon.fetch,
    "eightfold": eightfold.fetch,
    "uber": uber.fetch,
    "microsoft": microsoft.fetch,
}

__all__ = ["REGISTRY"]
