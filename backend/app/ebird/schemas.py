"""Typed views of eBird API 2.0 responses. Only the fields we use are declared."""

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class _EBirdModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")


class EBirdObservation(_EBirdModel):
    species_code: str = Field(alias="speciesCode")
    common_name: str = Field(alias="comName")
    sci_name: str = Field(alias="sciName")
    loc_id: str | None = Field(default=None, alias="locId")
    loc_name: str | None = Field(default=None, alias="locName")
    obs_dt: datetime = Field(alias="obsDt")
    how_many: int | None = Field(default=None, alias="howMany")
    lat: float | None = None
    lng: float | None = None
    sub_id: str = Field(alias="subId")
    # Absent means not yet reviewed, never accepted
    is_valid: bool = Field(default=False, alias="obsValid")
    is_reviewed: bool = Field(default=False, alias="obsReviewed")
    location_private: bool = Field(default=True, alias="locationPrivate")  # fail closed

    @field_validator("obs_dt", mode="before")
    @classmethod
    def _parse_obs_dt(cls, v: object) -> object:
        # eBird sends "2026-11-18 08:15" or just "2026-11-18" when no time was recorded.
        if isinstance(v, str):
            fmt = "%Y-%m-%d %H:%M" if " " in v else "%Y-%m-%d"
            return datetime.strptime(v, fmt)
        return v

    @property
    def obs_date(self) -> date:
        return self.obs_dt.date()


class EBirdDailyStats(_EBirdModel):
    num_checklists: int = Field(alias="numChecklists")
    num_contributors: int = Field(alias="numContributors")
    num_species: int = Field(alias="numSpecies")


class EBirdTaxon(_EBirdModel):
    species_code: str = Field(alias="speciesCode")
    common_name: str = Field(alias="comName")
    sci_name: str = Field(alias="sciName")
    category: str
    taxon_order: float | None = Field(default=None, alias="taxonOrder")
    family_common_name: str | None = Field(default=None, alias="familyComName")
