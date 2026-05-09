"""ColorFlow 自定义异常"""


class ColorFlowError(Exception):
    """ColorFlow 基础异常"""
    pass


class ValidationError(ColorFlowError):
    """参数校验失败"""
    pass


class TraceError(ColorFlowError):
    """VTracer 执行失败"""
    pass
