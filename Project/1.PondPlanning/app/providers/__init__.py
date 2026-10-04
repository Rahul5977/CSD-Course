"""Adapters to external data sources, behind Protocols defined here.

``DEMProvider`` (Copernicus / ALOS / uploaded contour KML), ``RainfallProvider``
(IMD / Open-Meteo / NASA POWER), imagery. Swapping a provider must never require
an engine change — that substitutability is what makes the KML upload route a
thin adapter rather than a second pipeline.
"""
