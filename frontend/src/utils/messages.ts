import type { RuntimeContent, RuntimeMessage } from "../api/types";

const stringifyData = (value: unknown): string => {
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return String(value);
  }
};

const contentToText = (content: RuntimeContent): string => {
  switch (content.type) {
    case "text":
      return content.text ?? "";
    case "image":
      return content.image_url ? `[图片] ${content.image_url}` : "[图片]";
    case "file":
      return content.file_name
        ? `[文件] ${content.file_name}`
        : "[文件消息]";
    case "data":
      return `[结构化数据]\n${stringifyData(content.data)}`;
    default:
      return stringifyData(content);
  }
};

export const runtimeMessageToText = (message: RuntimeMessage): string => {
  if (!message.content?.length) {
    return "";
  }
  return message.content.map(contentToText).join("\n").trim();
};
