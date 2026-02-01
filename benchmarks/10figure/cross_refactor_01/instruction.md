# Cross-Repo Refactor: Standardize gRPC Health Check Service Field Name

## Objective

Rename the gRPC health check service name field to `grpc_service_name` consistently across both Envoy and Kubernetes. Currently, Envoy uses `service_name` and Kubernetes uses `service` for semantically identical fields — both specify the service name sent in the gRPC HealthCheckRequest.

## Context

Both Envoy and Kubernetes implement gRPC health checking per the gRPC health specification. However, they use different field names:

- **Envoy**: `GrpcHealthCheck.service_name` (in `api/envoy/config/core/v3/health_check.proto`)
- **Kubernetes**: `GRPCAction.Service` (in `staging/src/k8s.io/api/core/v1/types.go`)

This naming inconsistency makes it harder to reason about cross-project integrations. The task is to rename both to `grpc_service_name` and update all references.

## Task

### In Envoy (`/10figure/src/envoy/`)

1. Rename `service_name` to `grpc_service_name` in `api/envoy/config/core/v3/health_check.proto` (GrpcHealthCheck message)
2. Update the C++ member variable `service_name_` in `source/extensions/health_checkers/grpc/health_checker_impl.h`
3. Update all references in `source/extensions/health_checkers/grpc/health_checker_impl.cc`
4. Update test references in `test/common/upstream/health_checker_impl_test.cc`

### In Kubernetes (`/10figure/src/kubernetes/`)

1. Rename the `Service` field to `GRPCServiceName` in `staging/src/k8s.io/api/core/v1/types.go` (GRPCAction struct)
2. Update the gRPC prober: `pkg/probe/grpc/grpc.go`
3. Update the kubelet prober: `pkg/kubelet/prober/prober.go`
4. Update the apply configuration builder: `staging/src/k8s.io/client-go/applyconfigurations/core/v1/grpcaction.go`

Note: Generated files (generated.pb.go, zz_generated.deepcopy.go, zz_generated.conversion.go) would be auto-regenerated and should NOT be manually edited. Only edit source files.

## Expected Output

Generate a unified patch file at `/logs/agent/patch.diff` that renames the field across both repositories.

## Success Criteria

- Proto field renamed in Envoy health_check.proto
- C++ member and accessors renamed in Envoy health checker
- Go struct field renamed in Kubernetes types.go
- Go prober code updated to use new field name
- No references to old field names remain in edited files
- Patch applies cleanly to both repo directories

## Repos

- **Envoy** (C++/Proto): `/10figure/src/envoy/`
- **Kubernetes** (Go): `/10figure/src/kubernetes/`

## Time Limit

20 minutes

## Difficulty

Hard — requires finding all references across two large codebases in different languages
