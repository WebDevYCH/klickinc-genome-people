import { Combobox } from "../../../../ts-combobox";
import { IEventSystem } from "../../../../ts-common/events";
import { IHeaderFilter, HeaderFilterEvent, ICol, IRendererConfig, IComboFilterConfig } from "../../types";
export declare class ComboFilter implements IHeaderFilter {
    column: ICol;
    config: IRendererConfig;
    data: any[];
    value: string | string[];
    filterConfig: IComboFilterConfig;
    events: IEventSystem<HeaderFilterEvent>;
    private _filter;
    private _isFocused;
    constructor(column: any, config?: any, data?: any, value?: any, conf?: any);
    protected initFilter(): void;
    protected initHandlers(): void;
    getFilter(): Combobox;
    setValue(value: string | string[]): void;
    clear(): void;
    focus(): void;
    blur(): void;
}
