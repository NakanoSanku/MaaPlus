# Keep development tools outside the runtime core

MaaPlus will keep the normal runtime lightweight and place offline inspection, fixture replay,
recording adapters, and CLI tooling in the optional `maaplus[dev]` layer. The adapters will reuse
MaaFramework's debug, record, replay, and direct-recognition interfaces instead of implementing a
second controller or recognition engine; this preserves the small runtime dependency surface while
making the development workflow reproducible.
