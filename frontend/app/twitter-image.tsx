// twitter cards need their own image file; reuse the OpenGraph image
export { default, alt, size, contentType } from "./opengraph-image";

// must be declared here: next reads `runtime` from this file, not through re-exports
export const runtime = "edge";
