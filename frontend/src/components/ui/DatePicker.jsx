import { useState } from "react";
import { format, parseISO } from "date-fns";
import { Calendar as CalendarIcon } from "lucide-react";
import { Calendar } from "@/components/ui/calendar";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { todayLocalISO } from "@/lib/dateConstraints";

/**
 * DatePicker — shadcn Calendar inside a Popover, designed to drop in
 * wherever we previously used `<Input type="date" />`. By default it
 * disables every past date (purely visual; the parent should still
 * call validateFutureDateTime() on submit for defence-in-depth).
 *
 * Props:
 *  - value: "YYYY-MM-DD" string ("" or undefined for no date picked)
 *  - onChange: (newValue: "YYYY-MM-DD") => void
 *  - disablePast: boolean (default true)
 *  - blockedDates: string[] of ISO YYYY-MM-DD to grey out
 *  - placeholder, testid, className: passthrough
 */
export default function DatePicker({
  value,
  onChange,
  disablePast = true,
  blockedDates = [],
  placeholder = "Pick a date",
  testid,
  className,
  disabled = false,
}) {
  const [open, setOpen] = useState(false);
  const selected = value ? parseISO(value) : undefined;
  const todayIso = todayLocalISO();

  const isDisabled = (day) => {
    if (disablePast) {
      // Compare day's local YYYY-MM-DD with today
      const dayIso = format(day, "yyyy-MM-dd");
      if (dayIso < todayIso) return true;
      if (blockedDates.includes(dayIso)) return true;
    }
    return false;
  };

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button
          type="button"
          variant="outline"
          disabled={disabled}
          data-testid={testid}
          className={cn(
            "w-full justify-start text-left font-normal bg-black/40 border-white/10 text-white hover:bg-black/60 hover:text-white",
            !value && "text-neutral-500",
            className
          )}
        >
          <CalendarIcon className="mr-2 h-4 w-4 text-[#84CC16]" />
          {value ? format(selected, "EEE, d MMM yyyy") : <span>{placeholder}</span>}
        </Button>
      </PopoverTrigger>
      <PopoverContent
        align="start"
        className="w-auto p-0 bg-[#141414] border-white/10 text-white"
        data-testid={testid ? `${testid}-popover` : undefined}
      >
        <Calendar
          mode="single"
          selected={selected}
          onSelect={(d) => {
            if (!d) return;
            onChange(format(d, "yyyy-MM-dd"));
            setOpen(false);
          }}
          disabled={isDisabled}
          initialFocus
        />
      </PopoverContent>
    </Popover>
  );
}
