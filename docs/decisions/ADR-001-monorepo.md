# ADR-001 Monorepo

Status: accepted

The MVP uses a monorepo so contracts, rules, services, frontend, data and scripts can evolve together during the hackathon.

This reduces integration friction while preserving service boundaries through separate FastAPI apps and Dockerfiles.
