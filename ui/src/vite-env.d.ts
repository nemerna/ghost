/// <reference types="vite/client" />

// SVG module declarations
declare module '*.svg' {
  const content: string;
  export default content;
}

declare module '@patternfly/patternfly/assets/images/*.svg' {
  const content: string;
  export default content;
}
