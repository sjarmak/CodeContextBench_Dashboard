#include "NCCLUtils.hpp"
#include <stdexcept>

namespace c10d {

// Thread-safe method to check for async errors on the communicator
ncclResult_t NCCLComm::checkForAsyncErrors() {
  // Lock the mutex to ensure thread-safe access to ncclCommGetAsyncError
  std::lock_guard<std::mutex> lock(mutex_);

  ncclResult_t asyncError;
  ncclResult_t result = ncclCommGetAsyncError(comm_, &asyncError);

  if (result != ncclSuccess) {
    return result;
  }

  return asyncError;
}

// Helper function to check NCCL errors with thread safety
// This function can be used when you have external mutex management
ncclResult_t ncclGetAsyncErrorThreadSafe(ncclComm_t comm, std::mutex& mutex) {
  if (comm == nullptr) {
    return ncclInvalidArgument;
  }

  // Use lock_guard for RAII-style mutex management
  std::lock_guard<std::mutex> lock(mutex);

  ncclResult_t asyncError;
  ncclResult_t result = ncclCommGetAsyncError(comm, &asyncError);

  if (result != ncclSuccess) {
    return result;
  }

  return asyncError;
}

// Alternative implementation using unique_lock for more flexibility
class ScopedNCCLErrorCheck {
 public:
  ScopedNCCLErrorCheck(ncclComm_t comm, std::mutex& mutex)
      : comm_(comm), lock_(mutex) {}

  ncclResult_t check() {
    ncclResult_t asyncError;
    ncclResult_t result = ncclCommGetAsyncError(comm_, &asyncError);

    if (result != ncclSuccess) {
      return result;
    }

    return asyncError;
  }

 private:
  ncclComm_t comm_;
  std::unique_lock<std::mutex> lock_;
};

} // namespace c10d
