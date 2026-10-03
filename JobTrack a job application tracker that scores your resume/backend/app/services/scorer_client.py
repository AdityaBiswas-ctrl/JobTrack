import time
from typing import Any

import httpx
from pydantic import BaseModel, ConfigDict, Field, ValidationError


class ScorerResponse(BaseModel):
    status: str = Field(pattern="^success$")
    filename: str
    similarity_score: float = Field(ge=0, le=100)
    rating: str
    matched_keywords: list[str]
    missing_keywords: list[str]
    resume_keyword_count: int = Field(ge=0)
    jd_keyword_count: int = Field(ge=0)

    model_config = ConfigDict(extra="ignore")


class ScorerTimeout(Exception):
    pass


class ScorerError(Exception):
    pass


class ScorerClient:
    def __init__(
        self,
        base_url: str,
        timeout_seconds: float,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.transport = transport

    def score(self, filename: str, pdf_bytes: bytes, job_description: str) -> ScorerResponse:
        if not self.base_url:
            raise ScorerError("Scorer service is not configured")

        with httpx.Client(
            timeout=self.timeout_seconds,
            transport=self.transport,
        ) as client:
            for attempt in range(2):
                try:
                    response = client.post(
                        f"{self.base_url}/score",
                        files={
                            "resume_file": (
                                filename,
                                pdf_bytes,
                                "application/pdf",
                            )
                        },
                        data={"job_description": job_description},
                    )
                except httpx.TimeoutException as exc:
                    if attempt == 0:
                        time.sleep(0.1)
                        continue
                    raise ScorerTimeout("Scorer timed out after retrying once") from exc
                except httpx.HTTPError as exc:
                    raise ScorerError("Could not communicate with scorer service") from exc

                if response.status_code >= 500 and attempt == 0:
                    time.sleep(0.1)
                    continue
                if response.status_code >= 500:
                    raise ScorerError("Scorer service returned a server error")
                if response.is_error:
                    raise ScorerError(
                        f"Scorer rejected the request with HTTP {response.status_code}"
                    )

                try:
                    data: Any = response.json()
                    return ScorerResponse.model_validate(data)
                except (ValueError, ValidationError) as exc:
                    raise ScorerError("Scorer returned an invalid response") from exc

        raise ScorerError("Scorer request did not complete")
