#pragma once

#include <nccl.h>
#include <mutex>
#include <memory>

namespace c10d {

// Forward declaration
class NCCLComm;

// NCCL Communicator wrapper with thread safety
class NCCLComm {
 public:
  NCCLComm() : comm_(nullptr) {}

  explicit NCCLComm(ncclComm_t comm) : comm_(comm) {}

  ~NCCLComm() {
    if (comm_ != nullptr) {
      ncclCommDestroy(comm_);
    }
  }

  // Get the underlying NCCL communicator
  ncclComm_t getNcclComm() const {
    return comm_;
  }

  // Thread-safe method to check for async errors
  ncclResult_t checkForAsyncErrors();

  // Get the mutex for external synchronization if needed
  std::mutex& getMutex() {
    return mutex_;
  }

 private:
  ncclComm_t comm_;
  std::mutex mutex_;  // Protects access to ncclCommGetAsyncError
};

// Helper function to check NCCL errors with thread safety
ncclResult_t ncclGetAsyncErrorThreadSafe(ncclComm_t comm, std::mutex& mutex);

} // namespace c10d
