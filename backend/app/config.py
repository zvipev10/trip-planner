import json
import os

from .graphhopper import GraphHopperProvider, Profile
from .models import RoadPolicy
from .routino import RoutinoProvider
from .provider import PlanningError, UnconfiguredProvider


def configured_provider():
    if os.getenv("ROUTING_PROVIDER", "unconfigured") == "unconfigured":
        return UnconfiguredProvider()
    if os.getenv("ROUTING_PROVIDER") == "routino":
        try:
            return RoutinoProvider(os.environ["ROUTINO_BINARY"], os.environ["ROUTINO_DATABASE"], os.environ["ROUTINO_PROFILES"], os.environ["ROUTINO_TRANSLATIONS"])
        except KeyError:
            raise PlanningError("provider_configuration_error", "Configure the Routino binary, database, profiles and translations paths.", 503) from None
    if os.getenv("ROUTING_PROVIDER") != "graphhopper":
        raise PlanningError("provider_configuration_error", "Unknown routing provider.", 503)
    # This records an external validation outcome, not automatic certification.
    if os.getenv("GRAPHHOPPER_DISTANCE_VALIDATED", "false").lower() != "true":
        raise PlanningError("distance_profile_unvalidated", "Validate the GraphHopper distance profile before enabling trip calculations.", 503)
    try:
        raw = json.loads(os.environ["GRAPHHOPPER_PROFILES_JSON"])
        profiles = [Profile(name=item["name"], policy=RoadPolicy.model_validate(item["roadPolicy"])) for item in raw]
        if not profiles or any(not isinstance(p.name, str) or not p.name.strip() for p in profiles):
            raise ValueError()
        policies = [p.policy.model_dump_json() for p in profiles]
        if len(policies) != len(set(policies)):
            raise ValueError()
        return GraphHopperProvider(profiles, os.getenv("GRAPHHOPPER_API_KEY", ""), os.getenv("GRAPHHOPPER_BASE_URL", "https://graphhopper.com/api/1"))
    except (KeyError, ValueError, TypeError):
        raise PlanningError("provider_configuration_error", "GraphHopper profile configuration is invalid.", 503) from None
