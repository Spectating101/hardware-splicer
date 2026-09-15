// Derived-surrogate SPI flash oracle for Hardware Splicer virtual-lab testing.
// NOT a Winbond model. NOT eligible for manufacturer-model campaign credit.
`timescale 1ns/1ps

module hs_w25q_readonly_oracle(
    input  wire cs_n,
    input  wire sclk,
    input  wire mosi,
    output reg  miso
);
    reg [7:0] command;
    reg [7:0] out_byte;
    integer in_bits;
    integer out_bits;
    integer jedec_index;

    initial begin
        command = 8'h00;
        out_byte = 8'h00;
        in_bits = 0;
        out_bits = 0;
        jedec_index = 0;
        miso = 1'bz;
    end

    always @(posedge cs_n) begin
        command <= 8'h00;
        in_bits <= 0;
        out_bits <= 0;
        jedec_index <= 0;
        miso <= 1'bz;
    end

    always @(posedge sclk) begin
        if (!cs_n && in_bits < 8) begin
            command <= {command[6:0], mosi};
            in_bits <= in_bits + 1;
        end
    end

    always @(negedge sclk) begin
        if (!cs_n && in_bits >= 8) begin
            if (command == 8'h9F) begin
                case (jedec_index)
                    0: out_byte = 8'hEF;
                    1: out_byte = 8'h60;
                    default: out_byte = 8'h18;
                endcase
                miso <= out_byte[7-out_bits];
                if (out_bits == 7) begin
                    out_bits <= 0;
                    if (jedec_index < 2) jedec_index <= jedec_index + 1;
                end else begin
                    out_bits <= out_bits + 1;
                end
            end else begin
                miso <= 1'b0;
            end
        end
    end
endmodule
