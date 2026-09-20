export type Mp4VideoCodec = "avc" | "hevc" | "unknown";

const LABELS: Record<Mp4VideoCodec, string> = {
  avc: "H.264 (AVC)",
  hevc: "H.265 (HEVC)",
  unknown: "不明",
};

export const codecLabel = (codec: Mp4VideoCodec): string => LABELS[codec];

const SAMPLE_BYTES = 1024 * 1024;

async function readText(blob: Blob): Promise<string> {
  const buffer = await blob.arrayBuffer();
  return new TextDecoder("latin1").decode(new Uint8Array(buffer));
}

/**
 * MP4 の映像コーデックを判定する。
 * 映像の情報（moov）は先頭にも末尾にもあり得るため、両端を調べる。
 */
export async function detectMp4VideoCodec(file: File): Promise<Mp4VideoCodec> {
  const head = await readText(file.slice(0, Math.min(file.size, SAMPLE_BYTES)));
  const tail = file.size > SAMPLE_BYTES ? await readText(file.slice(file.size - SAMPLE_BYTES)) : "";
  const text = head + tail;
  const hasHevc = ["hvc1", "hev1", "hvcC", "hevC"].some((tag) => text.includes(tag));
  const hasAvc = ["avc1", "avc3", "avcC"].some((tag) => text.includes(tag));
  if (hasHevc && !hasAvc) {
    return "hevc";
  }
  if (hasAvc) {
    return "avc";
  }
  return "unknown";
}

export const HEVC_UPLOAD_WARNING =
  "H.265 (HEVC) の動画は iPhone のブラウザでは再生できません。H.264 (libx264) でエンコードし直してください。";

export const HEVC_PLAYBACK_ERROR =
  "H.265 (HEVC) の動画は iPhone のブラウザでは再生できません。H.264 (libx264) で再エンコードした MP4 を登録してください。";

export const ffmpegH264Command = (input = "input.mp4", output = "output.mp4"): string =>
  `ffmpeg -i ${input} -c:v libx264 -profile:v main -level 4.0 -pix_fmt yuv420p -c:a aac -movflags +faststart ${output}`;
