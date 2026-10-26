# Technical Specification (Spec) - Ingestion Edge
## System Ingress
- Protocol: HTTP/JSON stream handling over localhost loop back interfaces.
- Interception Baseline: Any transaction telemetry structure matching known anomaly flags triggers a 403 Forbidden.
- Target Metric Level: Latency bounds under <5.000000ms for edge containment.
