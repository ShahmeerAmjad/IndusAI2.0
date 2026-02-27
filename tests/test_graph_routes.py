"""Tests for graph API routes."""

import pytest


def test_graph_routes_module_imports():
    from routes.graph import router
    assert router.prefix == "/api/v1/graph"
