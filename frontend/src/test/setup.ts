import '@testing-library/jest-dom/vitest'

// jsdom 未实现 Element.prototype.scrollIntoView，组件中调用会抛错，统一打桩
if (!Element.prototype.scrollIntoView) {
  Element.prototype.scrollIntoView = function scrollIntoView() {}
}
