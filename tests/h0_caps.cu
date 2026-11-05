// Gate H0 capability query (no timing, no allocation): prints the device attributes that decide whether the
// GPU can fault on system-allocated (malloc'd, HMM) memory, and the driver and runtime versions. Run once.
#include <cstdio>
#include <cuda_runtime.h>
int main() {
    int dev = 0, v = 0, drv = 0, rt = 0;
    cudaGetDevice(&dev);
    cudaDeviceProp p; cudaGetDeviceProperties(&p, dev);
    printf("device %d: %s (sm_%d%d)\n", dev, p.name, p.major, p.minor);
    cudaDeviceGetAttribute(&v, cudaDevAttrPageableMemoryAccess, dev);
    printf("cudaDevAttrPageableMemoryAccess = %d\n", v);
    cudaDeviceGetAttribute(&v, cudaDevAttrPageableMemoryAccessUsesHostPageTables, dev);
    printf("cudaDevAttrPageableMemoryAccessUsesHostPageTables = %d\n", v);
    cudaDeviceGetAttribute(&v, cudaDevAttrConcurrentManagedAccess, dev);
    printf("cudaDevAttrConcurrentManagedAccess = %d\n", v);
    cudaDriverGetVersion(&drv); cudaRuntimeGetVersion(&rt);
    printf("CUDA driver version = %d, runtime version = %d\n", drv, rt);
    return 0;
}
