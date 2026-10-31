import { contextNumbers, contextYesNo } from './calibrationScales'

/** The answered fields of the context form, as the API expects them. */
export function contextPayload(values: Record<string, FormDataEntryValue>) {
  const data: Record<string, unknown> = {}
  for (const item of contextYesNo) if (values[item.name]) data[item.name] = values[item.name]
  if (values.hunger) data.hunger = values.hunger
  if (values.hormonal_context) data.hormonal_context = values.hormonal_context
  for (const item of contextNumbers) {
    if (values[item.name] !== '' && values[item.name] !== undefined) {
      data[item.name] = Number(values[item.name])
    }
  }
  if (values.ambient_odor_detail) data.ambient_odor_detail = values.ambient_odor_detail
  if (values.note) data.note = values.note
  return data
}
