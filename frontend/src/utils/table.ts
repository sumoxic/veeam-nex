/**
 * el-table 的行类型收窄。
 *
 * el-table-column 的插槽行在类型层面是宽松的 `Record<PropertyKey, any>`，
 * 而列组件的泛型无法从父级 `:data` 反推具体行类型，直接把 row 传给
 * 形参为具体接口的函数会报错。业务代码统一用 asRow<T>() 显式收窄，
 * 收窄之后字段依然是完整类型化的。
 */
export function asRow<T>(row: unknown): T {
  return row as T
}
