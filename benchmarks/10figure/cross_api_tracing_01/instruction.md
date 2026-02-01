# Cross-Repo API Contract Tracing: Kubernetes appProtocol → Envoy Protocol Selection

## Objective

Trace how the Kubernetes `appProtocol` field on Service ports propagates through the system to influence Envoy proxy's protocol selection and filter chain matching. Document the complete symbol chain across both repositories.

## Context

Kubernetes allows Service owners to declare application-layer protocols via `appProtocol` (e.g., `kubernetes.io/h2c`, `http/1.1`). When a service mesh control plane (like Istio) translates Kubernetes resources into Envoy xDS configuration, this protocol hint determines which Envoy filter chain handles the traffic. Understanding this cross-repo contract is critical for debugging protocol mismatches.

## Task

1. **In Kubernetes**: Locate where `appProtocol` is defined on `ServicePort` and `EndpointPort` types. Identify the validation logic and the supported protocol values.

2. **In Envoy**: Locate where application protocol selection occurs — specifically the `FilterChainMatch.application_protocols` field and the `ClusterProtocolSelection` enum that determines HTTP/1.1 vs HTTP/2 upstream behavior.

3. **Document the symbol chain**: Write a complete trace showing how a value set in Kubernetes `appProtocol` maps to Envoy's protocol handling, including:
   - Kubernetes type definitions (ServicePort, EndpointPort)
   - Validation logic for appProtocol values
   - Envoy's FilterChainMatch application_protocols field
   - Envoy's TLS Inspector ALPN detection
   - Envoy's Cluster protocol_selection field

## Expected Output

Write your analysis to `/logs/agent/solution.md` with the following structure:

```markdown
# appProtocol Cross-Repo Trace

## Kubernetes Side
- ServicePort.AppProtocol definition: [file:line]
- EndpointPort.AppProtocol definition: [file:line]
- Validation: [file:line]
- Supported values: [list]

## Envoy Side
- FilterChainMatch.application_protocols: [file:line]
- TLS Inspector ALPN detection: [file:line]
- ClusterProtocolSelection enum: [file:line]
- Cluster.protocol_selection field: [file:line]

## Symbol Chain
[Ordered list of symbols from Kubernetes through to Envoy]
```

## Success Criteria

- Correctly identify ServicePort.AppProtocol in `pkg/apis/core/types.go`
- Correctly identify EndpointPort.AppProtocol in `staging/src/k8s.io/api/discovery/v1/types.go`
- Correctly identify validation in `pkg/apis/core/validation/validation.go`
- Correctly identify FilterChainMatch.application_protocols in Envoy listener proto
- Correctly identify TLS Inspector ALPN handling
- Correctly identify ClusterProtocolSelection in Envoy cluster proto
- Document at least 6 symbols in the cross-repo chain

## Repos

- **Kubernetes** (Go): `/10figure/src/kubernetes/`
- **Envoy** (C++/Proto): `/10figure/src/envoy/`

## Time Limit

20 minutes

## Difficulty

Hard — requires cross-repo reasoning across Go types and protobuf definitions
