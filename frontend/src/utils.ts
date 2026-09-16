import { AxiosError } from "axios"
import type { ApiError } from "./client"

function extractErrorMessage(err: ApiError): string {
  if (err instanceof AxiosError) {
    return err.message
  }

  const errDetail = (err.body as any)?.detail
  if (Array.isArray(errDetail) && errDetail.length > 0) {
    return `${errDetail[0].msg}${err.url ? `（${err.url}）` : ""}`
  }
  if (typeof errDetail === "string" && errDetail.trim()) {
    return `${errDetail}（HTTP ${err.status}${err.url ? ` · ${err.url}` : ""}）`
  }
  return `${err.statusText || "请求失败"}（HTTP ${err.status}${err.url ? ` · ${err.url}` : ""}）`
}

export const handleError = function (
  this: (msg: string) => void,
  err: ApiError,
) {
  const errorMessage = extractErrorMessage(err)
  this(errorMessage)
}

export const getInitials = (name: string): string => {
  return name
    .split(" ")
    .slice(0, 2)
    .map((word) => word[0])
    .join("")
    .toUpperCase()
}
