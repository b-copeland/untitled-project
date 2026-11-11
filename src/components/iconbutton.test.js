import React from "react";
import { render, screen, fireEvent } from "@testing-library/react";
import { BsEye } from "react-icons/bs";
import { IconButton } from "./iconbutton";

test("an icon button is found and described by its label, not its icon", () => {
    const onClick = jest.fn();
    render(<IconButton icon={BsEye} label="View" onClick={onClick} />);

    const button = screen.getByRole("button", { name: "View" });
    expect(button.title).toBe("View");
    expect(button.textContent).toBe("");  // nothing but the icon
    fireEvent.click(button);
    expect(onClick).toHaveBeenCalledTimes(1);
});

test("a disabled icon button does nothing", () => {
    const onClick = jest.fn();
    render(<IconButton icon={BsEye} label="Pin" onClick={onClick} disabled />);
    fireEvent.click(screen.getByRole("button", { name: "Pin" }));
    expect(onClick).not.toHaveBeenCalled();
});
