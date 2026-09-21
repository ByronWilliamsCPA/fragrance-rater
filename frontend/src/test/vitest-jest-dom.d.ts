// #EDGE: frontend-tests: jest-dom@7.0.1's vitest.d.ts declares Assertion<T> with one
// type parameter; Vitest 5 requires Assertion<R, T> with two, so TypeScript's
// declaration merge silently drops jest-dom's matcher types under `expect()`.
// #VERIFY: remove this override once testing-library/jest-dom#738 ships a fix
// upstream (https://github.com/testing-library/jest-dom/issues/738).
import { expect } from 'vitest'
import type { TestingLibraryMatchers } from '@testing-library/jest-dom/matchers'

declare module 'vitest' {
  // This interface augmentation has an empty body by design: it only exists to
  // perform TypeScript declaration merging against vitest's own `Assertion`
  // interface, the same pattern jest-dom itself uses for Jest (types/jest.d.ts)
  // and would use here if its own vitest.d.ts had the correct arity. `T` is
  // unused in the body, but declaration merging requires this interface's type
  // parameter list to match vitest's `Assertion<R, T>` exactly, so it must be
  // re-declared even though only `R` is passed through to the matchers.
  // eslint-disable-next-line @typescript-eslint/no-empty-object-type, @typescript-eslint/no-unused-vars
  interface Assertion<R extends void | Promise<void> = void, T = unknown>
    extends TestingLibraryMatchers<ReturnType<typeof expect.stringContaining>, R> {}
}
